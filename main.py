import os
import json
import requests
import threading
import time
import random
from flask import Flask
import telebot

# Safe import - won't crash if missing
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

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "6056506592:AAEJXkeRbPnt4UXRjUn_WsFowaiEL7lemxA")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
OWNER_ID = 7428650018
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

print("TICKY PRIME STARTING ☠️💎")

# Flask for Render - keeps alive
app = Flask(__name__)
@app.route('/')
def home():
    return f"Ticky Prime LIVE 🤑 | Math:{MATH_READY} XAU:{XAU_READY} | Ashburn US"

def run_web():
    app.run(host='0.0.0.0', port=10000)

# Memory - no Firebase!
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

# Ticky Prime Personality - MONEY KING 🤑
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
        return f"Yo bro brain lagged 😅 {str(e)[:100]} Try again 🫴"

# Telegram Bot - SIMPLE NO FAIL!
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_message(message):
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        chat_id = message.chat.id
        print(f"Msg from {user_id}: {text[:50]}")

        if not text:
            return

        time.sleep(random.uniform(0.5, 1.2))

        # Math Brain check
        if MATH_READY and MATH_BRAIN:
            try:
                math_result = MATH_BRAIN.parse_and_calc(text)
                if math_result is not None:
                    bot.reply_to(message, f"📌 {text}\n🫴 {math_result} 💯")
                    return
            except:
                pass

        # Gold price check
        if XAU_READY and XAU and any(w in text.lower() for w in ['gold price', 'xau price', 'xauusd now']):
            try:
                gold_data = XAU.get_price_and_log()
                if gold_data:
                    text = f"{text}\n[SYSTEM: Current live XAUUSD is {gold_data['price_pretty']} USD. Use this.]"
            except:
                pass

        reply = ask_ticky(chat_id, text)
        bot.reply_to(message, reply)

    except Exception as e:
        print(f"Handler error: {e}")

def run_bot():
    print("Ticky Prime polling STARTED 🤑")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Polling crash: {e}, restarting in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    # Start Flask in background
    threading.Thread(target=run_web, daemon=True).start()
    # Start bot (blocking)
    run_bot()
