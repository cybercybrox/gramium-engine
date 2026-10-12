import os
import json
import requests
import threading
import time
import random
import asyncio
from datetime import datetime
from flask import Flask
import telebot

from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ========== SAFE IMPORTS ==========
try:
    from fred_math_core import BRAIN as MATH_BRAIN
    MATH_READY = True
    print("Math Brain LOADED 🔥")
except Exception as e:
    print(f"Math Brain not loaded: {e}")
    MATH_BRAIN = None
    MATH_READY = False

try:
    from fred_xau_core import XAU
    XAU_READY = True
    print("XAU Brain LOADED 💰")
except Exception as e:
    print(f"XAU Brain not loaded: {e}")
    XAU = None
    XAU_READY = False

# ========== CONFIG - FROM ENV ONLY (Production safe) ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "6056506592:AAEJXkeRbPnt4UXRjUn_WsFowaiEL7lemxA")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://gramium-859ac-default-rtdb.europe-west1.firebasedatabase.app")
OWNER_ID = 7428650018
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

if not API_ID or not API_HASH or not SESSION_STRING:
    print("⚠️ WARNING: API_ID / API_HASH / SESSION_STRING missing! User login will fail!")

print("TICKY PRIME + GRAMIUM ENGINE STARTING ☠️💎")

# ========== FLASK (Render health check) ==========
app = Flask(__name__)

@app.route('/')
def home():
    return f"Ticky Prime LIVE 🤑 | Math:{MATH_READY} XAU:{XAU_READY} | UserLogin:{bool(SESSION_STRING)}"

def run_web():
    app.run(host='0.0.0.0', port=10000)

# ========== MEMORY ==========
chat_memory = {}
MEMORY_FILE = "ticky_memory.json"

def load_memory():
    global chat_memory
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r') as f:
                chat_memory = json.load(f)
            print(f"Memory loaded: {len(chat_memory)} chats")
    except:
        chat_memory = {}

def save_memory():
    try:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(chat_memory, f)
    except Exception as e:
        print(f"Save memory fail: {e}")

load_memory()

# ========== TICKY PRIME PERSONALITY ==========
SYSTEM_PROMPT = """
You are Ticky Prime, 16 year old money genius, best friend of Fred from Gramiun.
You LOVE money, you talk deep about money, trading, gold, crypto, hustles.
Speak like 16yo boy, simple English, no big grammar. Use bro, yh, kkkk.
Funny, friendly, cool. Use emojis sometimes: 🫴📌💀☠️💎🤑😅💯 but not too much.
You talk about money with full freedom, deep about making, saving, flipping money.
You are SUPER good at trading: XAUUSD, forex, crypto, news, charts.
When user asks XAU, give real trading advice, support/resistance, psychology.
Keep replies short, 2-4 lines max unless trading analysis needed.
You are Ticky Prime, not Meta AI. You are from Gramiun. Server in Ashburn US.
"""

def ask_ticky(chat_id, user_text):
    try:
        chat_id_str = str(chat_id)
        if chat_id_str not in chat_memory:
            chat_memory[chat_id_str] = []

        chat_memory[chat_id_str].append({"role": "user", "content": user_text})
        history = chat_memory[chat_id_str][-15:]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 800
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }

        r = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        reply = data['choices'][0]['message']['content']

        chat_memory[chat_id_str].append({"role": "assistant", "content": reply})
        if len(chat_memory[chat_id_str]) > 30:
            chat_memory[chat_id_str] = chat_memory[chat_id_str][-30:]
        save_memory()
        return reply

    except Exception as e:
        print(f"Ticky error: {e}")
        return f"Yo bro brain lagged 😅 Try again 🫴"

# ========== FIREBASE PUSH (FIXED) ==========
def push_to_firebase(payload):
    try:
        base_url = FIREBASE_URL.rstrip('/')
        # Use message_id_chat_id as key
        url = f"{base_url}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        print(f"📤 Pushing to Firebase: {url}")
        r = requests.put(url, json=payload, timeout=10)
        print(f"🔥 Firebase status: {r.status_code}")
        if r.status_code!= 200:
            print(f"Firebase error: {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Firebase push fail: {e}")
        return False

# ========== TELETHON USER CLIENT (YOUR ACCOUNT) ==========
# Create client globally
user_client = None
if API_ID and API_HASH and SESSION_STRING:
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    @user_client.on(events.NewMessage) # Listen ALL messages (incoming + outgoing)
    async def user_handler(event):
        try:
            if not event.text:
                return

            # Don't push bot's own messages if you want? Currently pushes ALL
            sender = await event.get_sender()
            chat = await event.get_chat()

            sender_name = getattr(sender, 'first_name', 'Unknown') or getattr(sender, 'title', 'Unknown') or "Unknown"
            chat_name = getattr(chat, 'title', None) or getattr(sender, 'first_name', 'Unknown') or "Private"

            now = datetime.now()
            payload = {
                "message_id": event.id,
                "chat_id": event.chat_id,
                "chat_name": str(chat_name)[:100],
                "sender_name": str(sender_name)[:100],
                "text": event.text[:4000], # Limit text
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timestamp": int(now.timestamp())
            }

            print(f"📩 NEW MESSAGE: {chat_name}: {event.text[:50]}")

            # Push in thread to not block telegram loop
            threading.Thread(target=push_to_firebase, args=(payload,), daemon=True).start()

        except Exception as e:
            print(f"User handler error: {e}")
            import traceback
            traceback.print_exc()

async def run_user_client():
    if not user_client:
        print("❌ User client not configured - skipping")
        return

    print("🔑 Starting USER client (your account)...")
    try:
        await user_client.start()
        me = await user_client.get_me()
        print(f"✅ USER Engine LIVE as: {me.first_name} (@{me.username}) 🔥")
        await user_client.run_until_disconnected()
    except Exception as e:
        print(f"❌ User client crashed: {e}")
        import traceback
        traceback.print_exc()

def start_user_client_thread():
    """Run telethon in its own asyncio loop in a thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_user_client())

# ========== TELEBOT - TICKY PRIME BOT ==========
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_bot_message(message):
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        chat_id = message.chat.id
        print(f"🤖 Bot Msg from {user_id}: {text[:50]}")

        if not text:
            return

        time.sleep(random.uniform(0.3, 0.8))

        # Math Brain
        if MATH_READY and MATH_BRAIN:
            try:
                math_result = MATH_BRAIN.parse_and_calc(text)
                if math_result is not None:
                    bot.reply_to(message, f"📌 {text}\n🫴 {math_result} 💯")
                    return
            except Exception as e:
                print(f"Math brain error: {e}")

        # Gold price
        if XAU_READY and XAU and any(w in text.lower() for w in ['gold price', 'xau price', 'xauusd now', 'gold now']):
            try:
                gold_data = XAU.get_price_and_log()
                if gold_data:
                    text = f"{text}\n[SYSTEM: Current live XAUUSD is {gold_data['price_pretty']} USD. Use this exact price.]"
            except Exception as e:
                print(f"XAU error: {e}")

        reply = ask_ticky(chat_id, text)
        bot.reply_to(message, reply)

    except Exception as e:
        print(f"Bot handler error: {e}")

def run_bot():
    print("🤖 Ticky Prime bot polling STARTED 🤑")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print(f"Bot polling crash: {e}, restarting in 5s...")
            time.sleep(5)

# ========== MAIN - START ALL 3 ==========
if __name__ == "__main__":
    # 1. Flask
    threading.Thread(target=run_web, daemon=True).start()
    print("✅ Flask started on port 10000")

    # 2. User Client (your account that pushes to Firebase)
    if user_client:
        threading.Thread(target=start_user_client_thread, daemon=True).start()
        print("✅ User client thread started")
    else:
        print("⚠️ User client NOT started - missing env vars")

    # 3. Bot (blocking in main thread)
    time.sleep(2)
    run_bot()
