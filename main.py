import os
import traceback
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# ✅ FIX 1: Import WhatsApp from pywa_async instead of pywa
from pywa_async import WhatsApp
from pywa.types import Message

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuration
SENDER_PHONE = "+6588531385"
chat_history = []
last_debug_info = "System initialized."

wa = WhatsApp(
    phone_id=os.getenv("WA_PHONE_ID"),
    token=os.getenv("WA_TOKEN"),
    verify_token=os.getenv("WA_VERIFY_TOKEN"),
    server=app,
    webhook_endpoint="/webhook",
)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    chat_display = "\n".join(chat_history) if chat_history else ""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "sender": SENDER_PHONE,
        "chat_content": chat_display,
        "debug_msg": last_debug_info
    })

@app.post("/manual-send")
async def manual_send(to_phone: str = Form(...), message: str = Form(...)):
    global last_debug_info
    target = "".join(filter(str.isdigit, to_phone))
    try:
        # ✅ FIX 2: Await async send_message call
        await wa.send_message(to=target, text=message)
        chat_history.append(f"OUT ({target}): {message}")
        last_debug_info = f"SUCCESS: Sent to {target}"
    except Exception as e:
        last_debug_info = f"SEND ERROR: {str(e)}\n{traceback.format_exc()}"

    return HTMLResponse("<script>window.location.href='/';</script>")

@app.post("/clear")
async def clear_chat():
    global chat_history
    chat_history = []
    return HTMLResponse("<script>window.location.href='/';</script>")

# ✅ FIX 3: Handler is async def — now compatible with pywa_async
@wa.on_message()
async def handle_incoming(client: WhatsApp, msg: Message):
    global last_debug_info
    try:
        sender_number = msg.from_user.wa_id
        incoming_text = f"IN ({sender_number}): {msg.text}"

        chat_history.append(incoming_text)
        last_debug_info = f"New message from {sender_number}"

        # ✅ FIX 4: Await async reply
        await msg.reply_text(f"Avatar Agentic AI received: {msg.text}")

    except Exception as e:
        last_debug_info = f"WEBHOOK ERROR: {str(e)}\n{traceback.format_exc()}"
        