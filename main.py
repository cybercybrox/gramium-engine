import os
import requests
import threading
import asyncio
from datetime import datetime
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- Flask keeps Render alive ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ENV ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")
FIREBASE_URL = os.getenv("FIREBASE_URL", "")

print(f"ENV CHECK -> API_ID:{bool(API_ID)} HASH:{bool(API_HASH)} SESSION:{bool(SESSION)} FB:{bool(FIREBASE_URL)}")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push_to_firebase(payload):
    try:
        url = f"{FIREBASE_URL.rstrip('/')}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        r = requests.put(url, json=payload, timeout=10)
        print(f"Pushed -> {r.status_code}")
    except Exception as e:
        print(f"Firebase fail: {e}")

@client.on(events.NewMessage)
async def handler(event):
    if not event.text:
        return
    try:
        sender = await event.get_sender()
        chat = await event.get_chat()
        sender_name = getattr(sender, 'first_name', 'Unknown') or "Unknown"
        chat_name = getattr(chat, 'title', sender_name) or sender_name

        print(f"NEW: {chat_name} - {event.text[:30]}")

        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": str(chat_name),
            "sender_name": str(sender_name),
            "text": event.text,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
        }
        # Run in thread so telegram loop not blocked
        threading.Thread(target=push_to_firebase, args=(payload,), daemon=True).start()
    except Exception as e:
        print(f"Handler error: {e}")

async def start_bot():
    await client.start()
    print(f"Engine LIVE as {(await client.get_me()).first_name}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(start_bot())
