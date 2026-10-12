from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio, threading
from datetime import datetime
from flask import Flask

API_ID = int(os.getenv("API_ID").strip())
API_HASH = os.getenv("API_HASH").strip()
SESSION = os.getenv("SESSION_STRING").strip()
FIREBASE_URL = os.getenv("FIREBASE_URL").strip()

print(f"ENV OK: {bool(API_ID)} {bool(API_HASH)} {bool(SESSION)} {FIREBASE_URL[:40]}")

app = Flask(__name__)

@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥"

def run_web():
    # FIX: Render needs PORT env, not 10000 fixed
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push(payload):
    try:
        base_url = FIREBASE_URL.rstrip('/')
        url = f"{base_url}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        print(f"Pushing to Firebase: {url}")
        r = requests.put(url, json=payload, timeout=10)
        print(f"Firebase status: {r.status_code}")
    except Exception as e:
        print(f"Push Fail: {e}")

@client.on(events.NewMessage)  # FIX: removed () - this was breaking
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
            "chat_name": str(chat_name),
            "sender_name": str(sender_name),
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
    me = await client.get_me()
    print(f"Connected as: {me.first_name}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
