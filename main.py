from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, requests, asyncio, threading
from datetime import datetime
import pytz
from flask import Flask

# === ENV ===
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
FIREBASE_URL = os.getenv("FIREBASE_URL")
CHANNEL = "@Global_Bullion_Syndicate"

print(f"DEBUG FIREBASE_URL loaded: {bool(FIREBASE_URL)}")

# === WEB SERVER FOR RENDER ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥"

def run_web():
    app.run(host='0.0.0.0', port=10000)

# === TELEGRAM CLIENT ===
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# === FIREBASE PUSH ===
def push(payload):
    try:
        base_url = FIREBASE_URL.rstrip('/')
        url = f"{base_url}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        print(f"Pushing to Firebase: {url}")
        r = requests.put(url, json=payload, timeout=10)
        print(f"Firebase status: {r.status_code} - {r.text[:150]}")
    except Exception as e:
        print(f"Fail: {e}")

# === MESSAGE LISTENER (Your old engine) ===
@client.on(events.NewMessage())
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
            "chat_name": chat_name,
            "sender_name": sender_name,
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

# === GRAMIUM SESSION POSTER ENGINE 🔥 ===
SESSIONS_NY = {
    "Sydney": {"open": "17:00", "emoji": "🇦🇺", "desc": "Asia Start"},
    "Tokyo": {"open": "19:00", "emoji": "🇯🇵", "desc": "Asian Volatility"},
    "London": {"open": "03:00", "emoji": "🇬🇧", "desc": "KING Session - High Volatility"},
    "New York": {"open": "08:00", "emoji": "🇺🇸", "desc": "BOSS Session - News Time"},
}

posted_today = set()

async def session_poster_engine():
    await asyncio.sleep(8)
    print("Session Poster LIVE 🔥")
    
    # === TEST MESSAGE ON STARTUP ===
    try:
        ny_tz = pytz.timezone("America/New_York")
        zim_tz = pytz.timezone("Africa/Harare")
        pak_tz = pytz.timezone("Asia/Karachi")
        now_utc = datetime.now(pytz.utc)
        ny_now = now_utc.astimezone(ny_tz)
        zim_now = now_utc.astimezone(zim_tz)
        pak_now = now_utc.astimezone(pak_tz)

        test_msg = f"""
🚀 GRAMIUM ENGINE ONLINE! ✅

Your trading clock is LIVE! ⏰

🕐 Current Times:
🇿🇼 Zim: {zim_now.strftime('%H:%M:%S %d %b')}
🇵🇰 Pak: {pak_now.strftime('%H:%M:%S %d %b')}
🇺🇸 NY: {ny_now.strftime('%H:%M:%S %d %b %Z')}

Bot will auto-post when sessions open! 🔥
Join: {CHANNEL}

#Gramium #XAUUSD #Live
"""
        await client.send_message(CHANNEL, test_msg)
        print("Test message sent to channel!")
    except Exception as e:
        print(f"Test send fail: {e}")

    while True:
        try:
            now_utc = datetime.now(pytz.utc)
            ny_tz = pytz.timezone("America/New_York")
            zim_tz = pytz.timezone("Africa/Harare")
            pak_tz = pytz.timezone("Asia/Karachi")
            
            ny_now = now_utc.astimezone(ny_tz)
            zim_now = now_utc.astimezone(zim_tz)
            pak_now = now_utc.astimezone(pak_tz)
            
            # --- WEEKEND LOGIC 🔒 ---
            # Market closed Fri 17:00 NY to Sun 17:00 NY
            is_weekend = False
            if ny_now.weekday() == 5: # Saturday
                is_weekend = True
            elif ny_now.weekday() == 6: # Sunday
                if ny_now.hour < 17: # Before Sunday 5pm NY, still closed
                    is_weekend = True
            elif ny_now.weekday() == 4 and ny_now.hour >= 17: # Friday after 5pm NY closed
                is_weekend = True

            if is_weekend:
                if "weekend" not in posted_today:
                    weekend_msg = f"""
🔒 MARKET LOCKED! ☠️

Gold market closed! Weekend! 😴
No XAUUSD moves!

🕐 Now:
🇿🇼 {zim_now.strftime('%A %H:%M')} Zim
🇵🇰 {pak_now.strftime('%A %H:%M')} Pak
🇺🇸 {ny_now.strftime('%A %H:%M %Z')} NY

Opens: Sunday 5PM NY / 11PM Zim 🇿🇼

Stay tuned! 👇
{CHANNEL}
"""
                    await client.send_message(CHANNEL, weekend_msg)
                    posted_today.add("weekend")
                    print("Posted WEEKEND LOCKED")
                await asyncio.sleep(60)
                continue
            else:
                # Weekday - clear weekend flag
                if "weekend" in posted_today:
                    posted_today.clear()

            # --- SESSION OPEN CHECK ---
            current_ny_time = f"{ny_now.hour:02d}:{ny_now.minute:02d}"
            
            for session, info in SESSIONS_NY.items():
                if info["open"] == current_ny_time:
                    key = f"{session}_{ny_now.date()}"
                    if key not in posted_today:
                        clean_msg = f"""
{info['emoji']} {session.upper()} OPEN! 🚀

{info['desc']}

🕐 Time Now:
🇿🇼 Zim: {zim_now.strftime('%H:%M')} CAT
🇵🇰 Pak: {pak_now.strftime('%H:%M')} PKT
🇺🇸 NY: {ny_now.strftime('%H:%M %Z')}

XAUUSD ready to move! 📈

👉 {CHANNEL}
"""
                        await client.send_message(CHANNEL, clean_msg)
                        posted_today.add(key)
                        print(f"Posted {session} OPEN - {current_ny_time} NY")

            await asyncio.sleep(30)

        except Exception as e:
            print(f"Poster error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(60)

# === MAIN ===
async def main():
    await client.start()
    print(f"Connected as: {(await client.get_me()).first_name}")
    # Start poster engine as background task
    asyncio.create_task(session_poster_engine())
    print("Engine LIVE + Poster LIVE 🔥🔥")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
