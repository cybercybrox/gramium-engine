from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio, threading
from datetime import datetime
from flask import Flask

# === IMPORT YOUR BRAIN ===
from fred_math_core import BRAIN

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
FIREBASE_URL = os.getenv("FIREBASE_URL")

print(f"DEBUG FIREBASE_URL loaded: {bool(FIREBASE_URL)}")
print(f"DEBUG Math Brain Loaded: {BRAIN is not None} 🔥")

app = Flask(__name__)

@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥 | Math Brain ACTIVE"

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

        text = event.text.strip()
        print(f"NEW MESSAGE DETECTED: {chat_name} -> {text[:50]}")

        # === GRAMIUM MATH BRAIN LOGIC ===
        calc_result = None
        is_calc_command = False

        # Check if user wants calc: /calc 5 + 5 OR 5 + 5 OR calc 5*5
        if text.lower().startswith(('/calc', 'calc')):
            is_calc_command = True
            calc_result = BRAIN.parse_and_calc(text)
            if calc_result is not None:
                await event.reply(f"🧠 Gramiun Math Brain:\n`{text}` = **{calc_result}**")
        else:
            # Auto-detect simple math like "5 + 5" in any chat
            maybe_math = BRAIN.parse_and_calc(text)
            if maybe_math is not None and len(text) < 20: # prevent false positives
                calc_result = maybe_math
                print(f"Math detected: {text} = {calc_result}")

        now = datetime.now()
        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": chat_name,
            "sender_name": sender_name,
            "text": text,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "math_result": calc_result if calc_result is not None else 0,
            "is_calc": is_calc_command
        }
        push(payload)
        print(f"NEW: {chat_name}: {text[:50]} | Calc: {calc_result}")

    except Exception as e:
        print(f"Handler error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await client.start()
    print("Engine LIVE 🔥 | Math Brain READY")
    print(f"Connected as: {(await client.get_me()).first_name}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
