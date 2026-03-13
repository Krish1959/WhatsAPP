import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pywa import WhatsApp
from pywa.types import Message

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuration
SENDER_PHONE = "+6588531385"
# We'll use a simple list to store the last few received messages for the UI
received_messages = []

wa = WhatsApp(
    phone_id=os.getenv("WA_PHONE_ID"),
    token=os.getenv("WA_TOKEN"),
    verify_token=os.getenv("WA_VERIFY_TOKEN"),
    server=app,
    webhook_endpoint="/webhook",
)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Join received messages into a single string for the text box
    messages_display = "\n".join(received_messages) if received_messages else "No messages received yet."
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "sender": SENDER_PHONE,
        "received_content": messages_display
    })

@app.post("/manual-send")
async def manual_send(to_phone: str = Form(...), message: str = Form(...)):
    target = "".join(filter(str.isdigit, to_phone))
    wa.send_message(to=target, text=message)
    # Redirect back home to see the updated UI
    return HTMLResponse("<script>window.location.href='/';</script>")

@wa.on_message()
def handle_incoming(client: WhatsApp, msg: Message):
    """This triggers when YOU text the bot"""
    display_text = f"From {msg.from_user.wa_id}: {msg.text}"
    
    # Add to our UI list (keep last 10)
    received_messages.insert(0, display_text)
    if len(received_messages) > 10:
        received_messages.pop()
        
    # The 'Echo' - The bot replies to you automatically
    msg.reply_text(f"Avatar Agentic AI received: {msg.text}")