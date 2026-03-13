import os
import traceback
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pywa import WhatsApp

app = FastAPI()

# Configuration pulled from your Render Environment
SENDER_PHONE = "+6588531385"
templates = Jinja2Templates(directory="templates")

# Initialize WhatsApp Client
try:
    wa = WhatsApp(
        phone_id=os.getenv("WA_PHONE_ID"),
        token=os.getenv("WA_TOKEN"),
        verify_token=os.getenv("WA_VERIFY_TOKEN"),
        server=app,
        webhook_endpoint="/webhook",
    )
except Exception as e:
    print(f"CRITICAL: WhatsApp Init Failed: {e}")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serves the manual messaging UI"""
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "sender": SENDER_PHONE,
        "debug_msg": "System Ready. Waiting for input..."
    })

@app.post("/manual-send", response_class=HTMLResponse)
async def manual_send(request: Request, to_phone: str = Form(...), message: str = Form(...)):
    """Handles the form submission and provides debug feedback"""
    debug_log = ""
    try:
        # Clean up phone number: remove '+' and spaces
        target = "".join(filter(str.isdigit, to_phone))
        debug_log += f"Processing target: {target}\n"
        
        # Attempt to send via WhatsApp Cloud API
        # Using pywa's send_message method
        response = wa.send_message(to=target, text=message)
        
        debug_log += f"SUCCESS! Message ID: {response}\n"
    except Exception as e:
        # Capture the specific error from Meta/Python for the UI
        debug_log += f"FAILED: {str(e)}\n"
        # Adds the specific line number where it failed
        debug_log += f"\nFull Traceback:\n{traceback.format_exc()}"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "sender": SENDER_PHONE,
        "debug_msg": debug_log,
        "last_to": to_phone,
        "last_msg": message
    })

@wa.on_message()
def handle_incoming(client: WhatsApp, msg):
    """Echo logic for incoming messages"""
    print(f"Incoming from {msg.from_user.wa_id}: {msg.text}")
    msg.reply_text(f"Avatar Agentic AI received: {msg.text}")
    