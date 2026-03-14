import os
import json
import traceback
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pywa_async import WhatsApp
from pywa.types import Message

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ── Configuration ──────────────────────────────────────────────
SENDER_PHONE    = os.getenv("WA_PHONE_ID", "Unknown")
WA_PHONE_ID     = os.getenv("WA_PHONE_ID")
WA_TOKEN        = os.getenv("WA_TOKEN")
WA_VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN")

chat_history   = []
debug_messages = ["[SYSTEM] Initialized. Waiting for events..."]
webhook_hits   = []          # raw webhook payloads for diagnostics

# ── PyWA Client ────────────────────────────────────────────────
wa = WhatsApp(
    phone_id       = WA_PHONE_ID,
    token          = WA_TOKEN,
    verify_token   = WA_VERIFY_TOKEN,
    server         = app,
    webhook_endpoint = "/webhook",
)

# ──────────────────────────────────────────────────────────────
# RAW WEBHOOK INSPECTOR
# Catches every POST to /webhook BEFORE pywa processes it.
# This tells us if Meta is delivering anything at all.
# ──────────────────────────────────────────────────────────────
@app.middleware("http")
async def log_webhook_hits(request: Request, call_next):
    if request.url.path == "/webhook":
        try:
            body_bytes = await request.body()
            body_text  = body_bytes.decode("utf-8", errors="replace")

            if request.method == "POST":
                webhook_hits.append(body_text)          # store raw payload
                debug_messages.append(
                    f"[RAW WEBHOOK HIT] Method=POST "
                    f"Body={body_text[:300]}"            # first 300 chars
                )

                # Check if it's actually a WhatsApp message object
                try:
                    payload = json.loads(body_text)
                    # Navigate to message text safely
                    entry   = payload.get("entry", [{}])[0]
                    changes = entry.get("changes", [{}])[0]
                    value   = changes.get("value", {})
                    msgs    = value.get("messages", [])
                    if msgs:
                        debug_messages.append(
                            f"[PAYLOAD] Message detected in raw body: "
                            f"{msgs[0].get('text',{}).get('body','(no text)')}"
                        )
                except Exception:
                    pass

            elif request.method == "GET":
                debug_messages.append(
                    f"[WEBHOOK VERIFY] GET hit — "
                    f"params={dict(request.query_params)}"
                )
        except Exception as ex:
            debug_messages.append(f"[MIDDLEWARE ERROR] {str(ex)}")

    response = await call_next(request)
    return response


# ──────────────────────────────────────────────────────────────
# MANUAL RAW WEBHOOK ENDPOINT  (/raw-webhook)
# Alternative: forward Meta there to rule out pywa routing issues
# ──────────────────────────────────────────────────────────────
@app.get("/raw-webhook")
async def raw_webhook_verify(request: Request):
    """Meta webhook verification (GET)."""
    params     = dict(request.query_params)
    mode       = params.get("hub.mode")
    token      = params.get("hub.verify_token")
    challenge  = params.get("hub.challenge")

    debug_messages.append(f"[RAW-GET] mode={mode} token={token}")

    if mode == "subscribe" and token == WA_VERIFY_TOKEN:
        debug_messages.append("[RAW-GET] Verification SUCCESS")
        return HTMLResponse(content=challenge, status_code=200)
    return JSONResponse({"error": "Forbidden"}, status_code=403)


@app.post("/raw-webhook")
async def raw_webhook_receive(request: Request):
    """Receive raw Meta payloads for debugging."""
    try:
        body = await request.json()
        debug_messages.append(f"[RAW-POST] {json.dumps(body)[:500]}")

        # Parse manually
        entry   = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})
        msgs    = value.get("messages", [])

        for m in msgs:
            sender = m.get("from", "unknown")
            text   = m.get("text", {}).get("body", "(non-text)")
            chat_history.append(f"IN ({sender}): {text}")
            debug_messages.append(f"[RAW MSG] From={sender} Text={text}")

    except Exception as ex:
        debug_messages.append(f"[RAW-POST ERROR] {str(ex)}")

    return JSONResponse({"status": "ok"})


# ──────────────────────────────────────────────────────────────
# PYWA MESSAGE HANDLER
# ──────────────────────────────────────────────────────────────
@wa.on_message()
async def handle_incoming(client: WhatsApp, msg: Message):
    """Triggered by pywa when a message arrives."""
    global debug_messages
    try:
        sender_number = msg.from_user.wa_id
        text          = msg.text if msg.text else "(non-text message)"

        log_entry = f"IN ({sender_number}): {text}"
        chat_history.append(log_entry)
        debug_messages.append(f"[PYWA HANDLER] {log_entry}")

        # Auto-reply
        await msg.reply_text(
            f"Avatar AI received: {text}"
        )
        debug_messages.append(
            f"[PYWA HANDLER] Auto-reply sent to {sender_number}"
        )

    except Exception as ex:
        err = traceback.format_exc()
        debug_messages.append(f"[HANDLER ERROR] {str(ex)}\n{err}")


# ──────────────────────────────────────────────────────────────
# MANUAL SEND
# ──────────────────────────────────────────────────────────────
@app.post("/manual-send")
async def manual_send(
    to_phone: str = Form(...),
    message:  str = Form(...),
):
    target = "".join(filter(str.isdigit, to_phone))
    try:
        await wa.send_message(to=target, text=message)
        chat_history.append(f"OUT ({target}): {message}")
        debug_messages.append(f"[SEND] SUCCESS → {target}")
    except Exception as ex:
        debug_messages.append(f"[SEND ERROR] {str(ex)}")

    return HTMLResponse("<script>window.location.href='/';</script>")


# ──────────────────────────────────────────────────────────────
# CLEAR CHAT
# ──────────────────────────────────────────────────────────────
@app.post("/clear")
async def clear_chat():
    global chat_history, debug_messages, webhook_hits
    chat_history   = []
    debug_messages = ["[SYSTEM] Chat cleared."]
    webhook_hits   = []
    return HTMLResponse("<script>window.location.href='/';</script>")


# ──────────────────────────────────────────────────────────────
# STATUS / DIAGNOSTICS PAGE  (/status)
# ──────────────────────────────────────────────────────────────
@app.get("/status")
async def status():
    """
    Open this URL in browser to see raw diagnostics.
    Tells you: env vars loaded, webhook hits received, messages parsed.
    """
    return JSONResponse({
        "env_check": {
            "WA_PHONE_ID_set"     : bool(WA_PHONE_ID),
            "WA_TOKEN_set"        : bool(WA_TOKEN),
            "WA_VERIFY_TOKEN_set" : bool(WA_VERIFY_TOKEN),
        },
        "webhook_hits_count" : len(webhook_hits),
        "last_webhook_hit"   : webhook_hits[-1][:500] if webhook_hits else "None",
        "debug_messages"     : debug_messages[-20:],   # last 20 entries
        "chat_history"       : chat_history[-10:],     # last 10 messages
    })


# ──────────────────────────────────────────────────────────────
# HOME PAGE
# ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    chat_display  = "\n".join(chat_history) if chat_history else ""
    debug_display = "\n".join(debug_messages[-10:])   # last 10 debug lines
    return templates.TemplateResponse("index.html", {
        "request"      : request,
        "sender"       : SENDER_PHONE,
        "chat_content" : chat_display,
        "debug_msg"    : debug_display,
    })