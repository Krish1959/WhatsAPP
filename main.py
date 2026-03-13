from fastapi import FastAPI
from pywa import WhatsApp

app = FastAPI()

# Configuration hardcoded as requested
# Using phone_id (not phone_number_id) to fix the TypeError
wa = WhatsApp(
    phone_id="999534356582792", 
    token="YOUR_PERMANENT_TOKEN_HERE",
    verify_token="AvatarAgenticAI_2026", 
    server=app,
    webhook_endpoint="/webhook",
)

@wa.on_message()
def handle_message(client: WhatsApp, msg):
    # Log incoming text to Render console
    print(f"Received message: {msg.text}")
    
    # Simple echo response
    msg.reply_text(f"Avatar Agentic AI (via +6588531385) received: {msg.text}")

@app.get("/")
def index():
    return {"status": "Avatar Agentic AI is Live", "sender": "+6588531385"}
