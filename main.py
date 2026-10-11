from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio, threading, random
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

@client.on(events.NewMessage(outgoing=True, incoming=True))
async def handler(event):
    try:
        if not event.text: 
            return
        
        text = event.text.strip()
        print(f"NEW MESSAGE: -> {text[:50]}")

        # ===== PRIVATE CALC MODE - .Calc =====
        is_calc_cmd = text.lower().startswith('.calc')
        
        if is_calc_cmd and MATH_READY and BRAIN:
            try:
                result = BRAIN.parse_and_calc(text)
                if result is not None:
                    # Human-like delay 1 to 2 seconds 😅
                    delay = random.uniform(1.0, 2.0)
                    print(f"Calc detected: {text} = {result} | Waiting {delay:.1f}s like human...")
                    await asyncio.sleep(delay)
                    
                    # Clean answer - 10 not 10.0 with your emojis 📌 🫴
                    reply_text = f"📌 {text}\n🫴 {result}"
                    # If you want ONLY answer, use: reply_text = f"{result}"
                    await event.reply(reply_text)
                    print(f"Replied privately, NOT pushing to Firebase 🔒")
                    return
                else:
                    await asyncio.sleep(1)
                    await event.reply(f"📌 {text}\n🫴 Oops can't parse that bro 😅")
                    return
            except Exception as e:
                print(f"Calc error: {e}")
                return

        # ===== NORMAL DUMP MODE - Still goes to Firebase =====
        sender = await event.get_sender()
        chat = await event.get_chat()
        sender_name = getattr(sender, 'first_name', 'Unknown') or "Unknown"
        chat_name = getattr(chat, 'title', sender_name) or sender_name
        
        now = datetime.now()
        payload = {
            "message_id": event.id,
            "chat_id": event.chat_id,
            "chat_name": chat_name,
            "sender_name": sender_name,
            "text": text,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "math_result": 0
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
