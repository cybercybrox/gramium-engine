from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio, threading
from datetime import datetime
from flask import Flask

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
FIREBASE_URL = os.getenv("FIREBASE_URL")

print(f"DEBUG FIREBASE_URL loaded: {bool(FIREBASE_URL)}")

app = Flask(__name__)

@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥"

def run_web():
    app.run(host='0.0.0.0', port=10000)

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push(payload):
    try:
        # Fix URL trailing slash
        base_url = FIREBASE_URL.rstrip('/')
        url = f"{base_url}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        print(f"Pushing to Firebase: {url}")
        r = requests.put(url, json=payload, timeout=10)
        print(f"Firebase status: {r.status_code} - {r.text[:150]}")
    except Exception as e:
        print(f"Fail: {e}")

@client.on(events.NewMessage())  # FIXED - Removed incoming=True
async def handler(event):
    try:
        if not event.text: 
            return
        sender = await event.get_sender()
        chat = await event.get_chat()
        sender_name = getattr(sender, 'first_name', 'Unknown') or "Unknown"
        chat_name = getattr(chat, 'title', sender_name) or sender_name
        
        print(f"NEW MESSAGE DETECTED: {chat_name}")
        
        now = datetime.now()
        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": chat_name,
            "sender_name": sender_name,
            "text": event.text,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        }
        push(payload)
        print(f"NEW: {chat_name}: {event.text[:50]}")
    except Exception as e:
        print(f"Handler error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await client.start()
    print("Engine LIVE 🔥")
    print(f"Connected as: {(await client.get_me()).first_name}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
