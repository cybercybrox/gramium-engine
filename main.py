from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio
from datetime import datetime

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
FIREBASE_URL = os.getenv("FIREBASE_URL")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push(payload):
    try:
        url = f"{FIREBASE_URL}/messages/{payload['message_id']}.json"
        requests.put(url, json=payload, timeout=10)
        print(f"Pushed: {payload['text'][:20]}")
    except Exception as e:
        print(f"Fail: {e}")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.text: return
    sender = await event.get_sender()
    chat = await event.get_chat()
    sender_name = getattr(sender, 'first_name', 'Unknown')
    chat_name = getattr(chat, 'title', sender_name)
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
    print(f"NEW: {chat_name}: {event.text}")

async def main():
    await client.start()
    print("Engine LIVE 🔥")
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
