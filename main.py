import os
from fastapi import FastAPI, Request, Response
from pywa import WhatsApp
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Initialize WhatsApp Client
wa = WhatsApp(
    phone_number_id=os.getenv("WA_PHONE_ID"),
    token=os.getenv("WA_TOKEN"),
    verify_token=os.getenv("WA_VERIFY_TOKEN"), # You make this up (e.g., "AvatarAgenticAI_2026")
    server=app,
    webhook_endpoint="/webhook",
)

@wa.on_message()
def handle_message(client: WhatsApp, msg):
    # This is where your Agentic Logic (LangChain) will eventually go!
    user_text = msg.text
    msg.reply_text(f"Avatar Agentic AI received: {user_text}")

@app.get("/")
def index():
    return {"status": "Avatar Agentic AI Backend is Online"}