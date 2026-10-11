from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio, threading
from datetime import datetime
from flask import Flask

# Safe import - won't crash if math file missing
try:
    from fred_math_core import BRAIN
    MATH_READY = True
    print("Math Brain LOADED 🔥")
except Exception as e:
    print(f"Math Brain not loaded: {e}")
    BRAIN = None
    MATH_READY = False

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
FIREBASE_URL = os.getenv("FIREBASE_URL")

print(f"DEBUG FIREBASE_URL loaded: {bool(FIREBASE_URL)}")

app = Flask(__name__)

@app.route('/')
def home():
    return f"Gramium Engine LIVE 🔥 | Math: {MATH_READY}"

def run_web():
    app.run(host='0.0.0.0', port=10000)

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def push(payload):
    try:
        base_url = FIREBASE_URL.rstrip('/')
        url = f"{base_url}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        print(f"Pushing to Firebase: {url}")
        r = requests.put(url, json=payload, timeout=10)
        print(f"Firebase status: {r.status_code} - {r.text[:150]}")
    except Exception as e:
        print(f"Fail: {e}")

@client.on(events.NewMessage())
async def handler(event):
    try:
        if not event.text: 
            return
        sender = await event.get_sender()
        chat = await event.get_chat()
        sender_name = getattr(sender, 'first_name', 'Unknown') or "Unknown"
        chat_name = getattr(chat, 'title', sender_name) or sender_name
        
        text = event.text
        print(f"NEW MESSAGE: {chat_name} -> {text[:50]}")

        calc_result = None
        if MATH_READY and BRAIN:
            try:
                calc_result = BRAIN.parse_and_calc(text)
                if calc_result is not None and text.lower().startswith(('/calc','calc')):
                    await event.reply(f"🧠 {text} = {calc_result}")
            except:
                calc_result = None
        
        now = datetime.now()
        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": chat_name,
            "sender_name": sender_name,
            "text": text,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "math_result": calc_result if calc_result is not None else 0
        }
        push(payload)
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
