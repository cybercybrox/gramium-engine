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
    return "Gramium Engine LIVE 🔥 - Listening to ALL"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")
FIREBASE_URL = os.getenv("FIREBASE_URL", "")

print(f"ENV: API_ID={bool(API_ID)} HASH={bool(API_HASH)} SESSION={bool(SESSION)} FB={FIREBASE_URL[:30]}")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push(payload):
    try:
        base = FIREBASE_URL.rstrip('/')
        url = f"{base}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        r = requests.put(url, json=payload, timeout=15)
        print(f"✅ PUSHED [{payload['chat_name']}] {r.status_code}")
    except Exception as e:
        print(f"❌ Firebase fail: {e}")

# FIXED: This will catch EVERYTHING
@client.on(events.NewMessage(incoming=True))
@client.on(events.NewMessage(outgoing=True))
async def handler(event):
    print(f"--- RAW EVENT RECEIVED --- chat_id={event.chat_id} is_group={event.is_group} is_channel={event.is_channel}")
    try:
        # Get chat safely
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', None) or str(event.chat_id)
        except:
            chat_title = str(event.chat_id)

        # Get sender safely - channels will fail, use chat title
        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', None) or getattr(sender, 'title', None) or "Unknown"
        except Exception:
            sender_name = chat_title

        # Get text - handles photo captions, docs, everything
        text = ""
        if event.text:
            text = event.text
        elif event.message and event.message.message:
            text = event.message.message
        elif event.message and event.message.caption:
            text = event.message.caption
        else:
            text = "[Media/No Text]"

        print(f"NEW MSG: [{chat_title}] {sender_name}: {text[:60]}")

        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": str(chat_title)[:100],
            "sender_name": str(sender_name)[:100],
            "text": str(text)[:4000],
            "is_group": bool(event.is_group),
            "is_channel": bool(event.is_channel),
            "is_private": bool(event.is_private),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "timestamp": int(datetime.now().timestamp())
        }
        
        # Push in background
        threading.Thread(target=push, args=(payload,), daemon=True).start()

    except Exception as e:
        print(f"❌ Handler crashed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await client.start()
    me = await client.get_me()
    print(f"🔥 Engine LIVE as {me.first_name} - @{me.username}")
    print(f"🔥 Now listening to ALL groups/channels...")
    # List dialogs to prove it's connected to groups
    count = 0
    async for d in client.iter_dialogs(limit=10):
        print(f"  Joined: {d.name} - {d.id} | Group:{d.is_group} Channel:{d.is_channel}")
        count += 1
    print(f"Total shown {count} dialogs")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
