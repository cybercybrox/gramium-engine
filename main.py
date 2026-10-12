import os
import requests
import threading
import asyncio
from datetime import datetime
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

app = Flask(__name__)
@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")
FIREBASE_URL = os.getenv("FIREBASE_URL", "")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push_to_firebase(payload):
    try:
        url = f"{FIREBASE_URL.rstrip('/')}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        r = requests.put(url, json=payload, timeout=10)
        print(f"Pushed {payload['chat_name']} -> {r.status_code}")
    except Exception as e:
        print(f"Firebase fail: {e}")

@client.on(events.NewMessage)
async def handler(event):
    try:
        # THIS FIXES CHANNEL/GROUP
        chat = await event.get_chat()
        chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', None) or "Unknown"
        
        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', None) or getattr(sender, 'title', None) or "Channel"
        except:
            sender_name = chat_name  # For channels, sender = channel itself

        text = event.text or event.message.message or ""  # captures captions too
        if not text:
            return

        print(f"NEW [{chat_name}] {sender_name}: {text[:40]}")

        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": str(chat_name),
            "sender_name": str(sender_name),
            "text": text,
            "is_channel": bool(event.is_channel),
            "is_group": bool(event.is_group),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
        }
        threading.Thread(target=push_to_firebase, args=(payload,), daemon=True).start()
    except Exception as e:
        print(f"Handler error: {e}")
        import traceback
        traceback.print_exc()

async def start_bot():
    await client.start()
    me = await client.get_me()
    print(f"Engine LIVE as {me.first_name}")
    print(f"Listening to ALL chats (private, groups, channels)...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(start_bot())
