import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pywa import WhatsApp

app = FastAPI()

# 1. Non-Secret Constants (Hardcoded)
SENDER_PHONE = "+6588531385"

# 2. Setup Jinja2 (expects a folder named 'templates')
templates = Jinja2Templates(directory="templates")

# 3. Initialize WhatsApp Client using Render ENV Variables
# We pull the specific keys you set up on Render
wa = WhatsApp(
    phone_id=os.getenv("WA_PHONE_ID"),
    token=os.getenv("WA_TOKEN"),
    verify_token=os.getenv("WA_VERIFY_TOKEN"), # Matches your Render spelling
    server=app,
    webhook_endpoint="/webhook",
)

# --- WEB UI ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serves the manual messaging UI from the templates folder"""
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "sender": SENDER_PHONE
    })

@app.post("/manual-send")
async def manual_send(to_phone: str = Form(...), message: str = Form(...)):
    """Handles the form submission from the UI"""
    # Clean up phone number: remove '+' and spaces
    target = "".join(filter(str.isdigit, to_phone))
    
    # Send the message using the cloud API
    wa.send_message(to=target, text=message)
    
    return {
        "status": "Message Sent!", 
        "from": SENDER_PHONE, 
        "to": target, 
        "content": message
    }

# --- WEBHOOK LOGIC ---

@wa.on_message()
def handle_incoming(client: WhatsApp, msg):
    """Automated logic for incoming messages"""
    print(f"Received text from {msg.from_user.wa_id}: {msg.text}")
    
    # Automated response
    msg.reply_text(f"Avatar Agentic AI received: {msg.text}")

@app.get("/status")
async def status():
    return {"status": "online", "active_number": SENDER_PHONE}