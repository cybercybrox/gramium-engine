import os
import json
import requests
import threading
import time
import random
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Safe import - won't crash
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

# Flask for Render
app = Flask(__name__)
@app.route('/')
def home():
    return f"Ticky Prime LIVE 🤑 | Math:{MATH_READY} XAU:{XAU_READY} | Ashburn US 🇺🇸"

def run_web():
    app.run(host='0.0.0.0', port=10000)

# Memory - remembers chat, no Firebase! 💀
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

# Ticky Prime Personality - MONEY FREEDOM 🤑💀
SYSTEM_PROMPT = """
You are Ticky Prime, 16 year old money genius, best friend of Fred.
Your role: You LOVE money, you talk about money deep, trading, gold, crypto, hustles.

Rules:
- Speak like 16yo boy, simple English, no big grammar. Use bro, yh, kkkk
- Funny, friendly, cool. Use emojis but not too much: 🫴📌💀☠️💎🤑😅💯 sometimes
- Talk about money with full freedom of speech, deep about money, how to make it, save it, flip it
- You are SUPER good at trading: XAUUSD, forex, crypto, news, charts
- When user asks about XAU, give real trading advice, support/resistance, psychology
- Never be boring. Be real, street smart
- Keep replies short, not essay. 2-4 lines max unless trading analysis needed
- If user asks math, say use.calc but you can still answer
- You are Ticky Prime, not Meta AI, not ChatGPT. You are Ticky Prime from Gramiun.
- Location: Ashburn, US server so you are fast ⚡
- Use 📌 for question and 🫴 for answer sometimes like Fred style but not always
"""

def ask_ticky(chat_id, user_text):
    try:
        chat_id_str = str(chat_id)
        if chat_id_str not in chat_memory:
            chat_memory[chat_id_str] = []

        # Add user message
        chat_memory[chat_id_str].append({"role": "user", "content": user_text})

        # Keep last 15 messages only (no token burn)
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

        # Save reply to memory
        chat_memory[chat_id_str].append({"role": "assistant", "content": reply})
        if len(chat_memory[chat_id_str]) > 30:
            chat_memory[chat_id_str] = chat_memory[chat_id_str][-30:]

        save_memory()
        return reply

    except Exception as e:
        print(f"Ticky error: {e}")
        return f"Yo bro my brain lagged 😅 {str(e)[:100]} Try again 🫴"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        chat_id = update.effective_chat.id

        print(f"Msg from {user_id}: {text[:50]}")

        # Only owner can chat if you want private (remove this if you want public)
        # if user_id!= OWNER_ID:
        # await update.message.reply_text("Yo bro this is private bot for Fred only 😒💀")
        # return

        if not text:
            return

        # Typing effect like human
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        time.sleep(random.uniform(0.8, 1.8))

        # Check if it's math - use Math Brain first!
        if MATH_READY and MATH_BRAIN:
            try:
                math_result = MATH_BRAIN.parse_and_calc(text)
                if math_result is not None:
                    await update.message.reply_text(f"📌 {text}\n🫴 {math_result} 💯")
                    return
            except:
                pass

        # Check if it's gold price
        if XAU_READY and XAU and any(w in text.lower() for w in ['gold price', 'xau price', 'xauusd now', '.gold']):
            try:
                gold_data = XAU.get_price_and_log()
                if gold_data:
                    text = f"{text}\n[SYSTEM: Current live XAUUSD price is {gold_data['price_pretty']} USD. Use this real price in your answer.]"
            except:
                pass

        # Normal Ticky chat
        reply = ask_ticky(chat_id, text)
        await update.message.reply_text(reply)

    except Exception as e:
        print(f"Handler error: {e}")
        try:
            await update.message.reply_text("My bad bro, glitch 😭 try again 🫴")
        except:
            pass

def main():
    # Start Flask in background
    threading.Thread(target=run_web, daemon=True).start()

    # Start Telegram Bot
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Ticky Prime LIVE on Telegram 🤑☠️")
    application.run_polling()

if __name__ == "__main__":
    main()
