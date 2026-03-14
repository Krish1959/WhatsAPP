import os
import json
import hmac
import hashlib
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ── Config ────────────────────────────────────────────────
WA_TOKEN        = os.getenv("WA_TOKEN", "")
WA_PHONE_ID     = os.getenv("WA_PHONE_ID", "")
VERIFY_TOKEN    = os.getenv("WA_VERIFY_TOKEN", "myverify123")
API_URL         = f"https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages"

# ── State ─────────────────────────────────────────────────
chat_history    = []
debug_log       = ["[SYSTEM] Initialized. Waiting for events..."]
webhook_hits    = 0

def ts():
    return datetime.now().strftime("%H:%M:%S")

def add_debug(msg: str):
    debug_log.append(f"[{ts()}] {msg}")
    # Keep last 20 debug entries
    if len(debug_log) > 20:
        debug_log.pop(0)

# ── Home Page ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    phone_display = WA_PHONE_ID[-6:] if WA_PHONE_ID else "NOT SET"
    return templates.TemplateResponse("index.html", {
        "request":      request,
        "sender":       phone_display,
        "chat_content": "\n".join(chat_history),
        "debug_msg":    " | ".join(debug_log[-5:])
    })

# ── Status Check ──────────────────────────────────────────
@app.get("/status")
async def status():
    return JSONResponse({
        "wa_phone_id_set":    bool(WA_PHONE_ID),
        "wa_token_set":       bool(WA_TOKEN),
        "verify_token_set":   bool(VERIFY_TOKEN),
        "wa_phone_id_value":  WA_PHONE_ID,
        "webhook_hits_count": webhook_hits,
        "chat_history_count": len(chat_history),
        "recent_debug":       debug_log[-10:]
    })

# ── Manual Send ───────────────────────────────────────────
@app.post("/manual-send")
async def manual_send(
    to_phone: str = Form(...),
    message:  str = Form(...)
):
    target = "".join(filter(str.isdigit, to_phone))
    
    payload = {
        "messaging_product": "whatsapp",
        "to": target,
        "type": "text",
        "text": {"body": message}
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type":  "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
        
        if resp.status_code == 200:
            chat_history.append(f"OUT ({target}): {message}")
            add_debug(f"[SEND] SUCCESS → {target}")
        else:
            err = resp.json()
            add_debug(f"[SEND FAIL] {resp.status_code}: {err.get('error',{}).get('message','unknown')}")
    
    except Exception as e:
        add_debug(f"[SEND ERROR] {str(e)}")
    
    return HTMLResponse("<script>window.location.href='/';</script>")

# ── Webhook Verification (GET) ────────────────────────────
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode      = params.get("hub.mode", "")
    token     = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")
    
    add_debug(f"[VERIFY] mode={mode} token_match={token==VERIFY_TOKEN}")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        add_debug("[VERIFY] ✅ Webhook verified!")
        return HTMLResponse(content=challenge, status_code=200)
    
    add_debug("[VERIFY] ❌ Token mismatch!")
    return HTMLResponse(content="Forbidden", status_code=403)

# ── Webhook Receiver (POST) ───────────────────────────────
@app.post("/webhook")
async def receive_webhook(request: Request):
    global webhook_hits
    webhook_hits += 1
    
    try:
        body = await request.json()
        add_debug(f"[WEBHOOK HIT #{webhook_hits}] Payload received")
        
        # Log raw payload for debugging
        raw_str = json.dumps(body)[:200]
        add_debug(f"[RAW] {raw_str}")
        
        # ── Parse WhatsApp message structure ──
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                
                # Check for incoming messages
                messages = value.get("messages", [])
                for msg in messages:
                    msg_type = msg.get("type", "")
                    from_num = msg.get("from", "unknown")
                    
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                        chat_history.append(f"IN ({from_num}): {text}")
                        add_debug(f"[IN] From {from_num}: {text[:50]}")
                        
                        # Auto-reply
                        await send_reply(from_num, f"Echo: {text}")
                    
                    elif msg_type == "image":
                        chat_history.append(f"IN ({from_num}): [Image received]")
                        add_debug(f"[IN] Image from {from_num}")
                    
                    else:
                        chat_history.append(f"IN ({from_num}): [{msg_type}]")
                        add_debug(f"[IN] {msg_type} from {from_num}")
                
                # Check for status updates
                statuses = value.get("statuses", [])
                for status in statuses:
                    st = status.get("status", "")
                    to = status.get("recipient_id", "")
                    add_debug(f"[STATUS] {st} → {to}")
        
        return JSONResponse({"status": "ok"}, status_code=200)
    
    except Exception as e:
        add_debug(f"[WEBHOOK ERROR] {str(e)}")
        return JSONResponse({"status": "error"}, status_code=200)
    # Always return 200 to prevent Meta retries

# ── Auto Reply Helper ─────────────────────────────────────
async def send_reply(to: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type":  "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
        if resp.status_code == 200:
            add_debug(f"[REPLY] Sent to {to}")
        else:
            add_debug(f"[REPLY FAIL] {resp.status_code}")
    except Exception as e:
        add_debug(f"[REPLY ERROR] {str(e)}")

# ── Clear Chat ────────────────────────────────────────────
@app.post("/clear")
async def clear_chat():
    global chat_history, webhook_hits
    chat_history  = []
    webhook_hits  = 0
    add_debug("[SYSTEM] Chat cleared")
    return HTMLResponse("<script>window.location.href='/';</script>")