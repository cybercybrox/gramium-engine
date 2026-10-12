import os
import requests
import threading
import asyncio
import logging
from datetime import datetime
import zoneinfo
import httpx
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Configure production logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- PYTHON 3.14 EVENT LOOP COMPATIBILITY FIX ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# --- GRAMIUM ENGINE ---
class GramiumEngine:
    def __init__(self, fred_api_key: str):
        self.fred_api_key = fred_api_key
        self.fred_url = "https://api.stlouisfed.org/fred/series/observations"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        
        self.metrics = {
            "DTWEXBGS": "Real USD Strength",
            "SOFR": "SOFR",
            "WALCL": "Total Assets",
            "RRPONTSYD": "Reverse Repo",
            "DGS10": "10-Year Treasury Yield"
        }

    async def _fetch_fred_series(self, client: httpx.AsyncClient, series_id: str) -> dict:
        params = {
            "series_id": series_id,
            "api_key": self.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 45
        }
        try:
            response = await client.get(self.fred_url, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            observations = data.get("observations", [])
            valid_obs = [o for o in observations if o.get("value") not in (".", None, "Unavailable")]
            
            if valid_obs:
                latest_val = float(valid_obs[0]["value"])
                historical_val = float(valid_obs[min(30, len(valid_obs) - 1)]["value"])
                change_pct = ((latest_val - historical_val) / historical_val) * 100 if historical_val != 0 else 0.0
                
                return {
                    "id": series_id,
                    "name": self.metrics.get(series_id, series_id),
                    "latest_value": latest_val,
                    "change_pct_30d": change_pct,
                    "date": valid_obs[0]["date"]
                }
        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            
        return {
            "id": series_id,
            "name": self.metrics.get(series_id, series_id),
            "latest_value": 0.0,
            "change_pct_30d": 0.0,
            "date": "N/A"
        }

    async def _fetch_gld_price(self, client: httpx.AsyncClient) -> float:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GLD"
        try:
            response = await client.get(url, headers=self.headers, timeout=5.0)
            data = response.json()
            return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
        except Exception as e:
            logger.error(f"Error fetching GLD price: {e}")
            return 0.0

    async def _fetch_xau_price(self, client: httpx.AsyncClient) -> float:
        url = "https://api.gold-api.com/price/XAU"
        try:
            response = await client.get(url, headers=self.headers, timeout=5.0)
            data = response.json()
            return float(data.get('price', 0.0))
        except Exception as e:
            logger.error(f"Error fetching XAU price: {e}")
            return 0.0

    def get_world_times(self) -> dict:
        now_utc = datetime.now(zoneinfo.ZoneInfo("UTC"))
        ny = now_utc.astimezone(zoneinfo.ZoneInfo("America/New_York"))
        pk = now_utc.astimezone(zoneinfo.ZoneInfo("Asia/Karachi"))
        zw = now_utc.astimezone(zoneinfo.ZoneInfo("Africa/Harare"))
        london = now_utc.astimezone(zoneinfo.ZoneInfo("Europe/London"))
        
        ny_hour = ny.hour + ny.minute / 60
        is_ny_open = 8.33 <= ny_hour <= 13.5
        
        return {
            "utc_date": now_utc.date(),
            "ny": ny,
            "pk": pk,
            "zw": zw,
            "london": london,
            "is_ny_open": is_ny_open,
            "fred_fetch_window": (zw.hour == 22 and zw.minute >= 25)
        }

    def calculate_bias(self, fred_dict: dict, gld_price: float, xau_price: float) -> tuple:
        score = 0
        reasons = []

        dtwex_change = fred_dict.get("DTWEXBGS", {}).get("change_pct_30d", 0.0)
        if dtwex_change > 1.0:
            score += 2
            reasons.append(f"USD strong (+{dtwex_change:.2f}%) = SELL")
        elif dtwex_change < -1.0:
            score -= 2
            reasons.append(f"USD weak ({dtwex_change:.2f}%) = BUY")

        dgs10_change = fred_dict.get("DGS10", {}).get("change_pct_30d", 0.0)
        if dgs10_change > 0:
            score += 1
            reasons.append("Yield up = SELL")

        rrp_change = fred_dict.get("RRPONTSYD", {}).get("change_pct_30d", 0.0)
        if rrp_change < -50:
            score += 1
            reasons.append(f"Cash pile drained ({rrp_change:.1f}%) = Risk On / Sell Gold")

        if gld_price > 0 and xau_price > 0:
            premium = xau_price - (gld_price * 10)
            premium_pct = (premium / xau_price) * 100
            if premium_pct > 5:
                score -= 1
                reasons.append(f"High physical premium ({premium_pct:.1f}%) = BUY")
            elif premium_pct < 2:
                score += 1
                reasons.append("Low physical premium = SELL")

        if score >= 2:
            bias = "🔴 SELL ONLY TODAY - Wait for setup then SELL"
        elif score <= -2:
            bias = "🟢 BUY ONLY TODAY"
        else:
            bias = "🟡 NEUTRAL - Stand aside"

        return bias, score, reasons

    async def execute_all(self) -> dict:
        async with httpx.AsyncClient() as client:
            fred_tasks = [self._fetch_fred_series(client, series_id) for series_id in self.metrics.keys()]
            fred_results, gld_price, xau_price = await asyncio.gather(
                asyncio.gather(*fred_tasks),
                self._fetch_gld_price(client),
                self._fetch_xau_price(client)
            )

        fred_dict = {item["id"]: item for item in fred_results}
        clock_data = self.get_world_times()
        bias, score, reasons = self.calculate_bias(fred_dict, gld_price, xau_price)

        return {
            "clock": clock_data,
            "fred": fred_dict,
            "gld": gld_price,
            "xau": xau_price,
            "bias": bias,
            "score": score,
            "reasons": reasons
        }


# --- FLASK KEEP-ALIVE SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Gramium Engine LIVE 🔥 - Running & Monitoring"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


# --- CONFIGURATION & INIT ---
API_ID_RAW = os.getenv("API_ID", "0")
API_ID = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")
FIREBASE_URL = os.getenv("FIREBASE_URL", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "950d24880df05b9e609f2927d3a1076b")

print(f"ENV CHECK: API_ID={bool(API_ID)} HASH={bool(API_HASH)} SESSION={bool(SESSION)} FB={bool(FIREBASE_URL)}")

if not API_ID or not API_HASH or not SESSION:
    print("❌ CRITICAL ERROR: Missing API_ID, API_HASH, or SESSION_STRING environment variables!")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH, loop=loop)
engine = GramiumEngine(FRED_API_KEY)


def push(payload):
    try:
        base = FIREBASE_URL.rstrip('/')
        url = f"{base}/messages/{payload['message_id']}_{payload['chat_id']}.json"
        r = requests.put(url, json=payload, timeout=15)
        print(f"✅ PUSHED [{payload['chat_name']}] {r.status_code}")
    except Exception as e:
        print(f"❌ Firebase fail: {e}")


# --- AUTOMATED BACKGROUND SCHEDULER (22:30 Harare Time) ---
async def scheduled_macro_notifier(telegram_client, macro_engine):
    last_sent_date = None
    print("⏰ Background macro scheduler started (Target: 22:30 Harare Time)")
    
    while True:
        try:
            now_zw = datetime.now(zoneinfo.ZoneInfo("Africa/Harare"))
            current_date = now_zw.date()
            
            # Triggers exactly at 22:30 once per day
            if now_zw.hour == 22 and now_zw.minute == 30 and last_sent_date != current_date:
                print("⚡ Scheduled time reached! Running Gramium Engine for nightly alert...")
                result = await macro_engine.execute_all()
                
                ny_time_str = result['clock']['ny'].strftime('%H:%M:%S')
                is_open_status = "OPEN 🟢" if result['clock']['is_ny_open'] else "CLOSED 🔴"
                reasons_bullet = "\n".join([f"• {r}" for r in result['reasons']]) if result['reasons'] else "• No strong factors triggered."
                
                alert_message = (
                    f"🔔 **TOMORROW MACRO BIAS ALERT** 🔔\n\n"
                    f"**Bias:** {result['bias']}\n"
                    f"**Score:** {result['score']}\n\n"
                    f"💰 **Gold (XAU):** ${result['xau']:,.2f}\n"
                    f"📉 **GLD Proxy:** ${result['gld']:,.2f}\n\n"
                    f"🔍 **Core Drivers:**\n{reasons_bullet}\n\n"
                    f"⏰ **Harare Time:** {now_zw.strftime('%H:%M:%S')} ({current_date})\n"
                    f"🏛️ **COMEX Session:** {is_open_status}"
                )
                
                # Send DM to yourself (Saved Messages)
                await telegram_client.send_message('me', alert_message)
                last_sent_date = current_date
                print("🚀 Successfully sent automated nightly bias alert to Saved Messages!")
                
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
            
        # Check time every 30 seconds
        await asyncio.sleep(30)


# --- TELEGRAM EVENT HANDLER ---
@client.on(events.NewMessage(incoming=True))
@client.on(events.NewMessage(outgoing=True))
async def handler(event):
    try:
        text = ""
        if event.text:
            text = event.text
        elif event.message and event.message.message:
            text = event.message.message
        elif event.message and event.message.caption:
            text = event.message.caption
        else:
            text = "[Media/No Text]"

        if "xauusd" in text.lower():
            print(f"⚡ XAUUSD trigger detected! Running Gramium Engine...")
            result = await engine.execute_all()
            
            ny_time_str = result['clock']['ny'].strftime('%H:%M:%S')
            ny_date_str = result['clock']['ny'].strftime('%Y-%m-%d')
            is_open_status = "OPEN 🟢" if result['clock']['is_ny_open'] else "CLOSED 🔴"
            
            reasons_bullet = "\n".join([f"• {r}" for r in result['reasons']]) if result['reasons'] else "• No strong factors triggered."
            
            response_message = (
                f"📊 **GRAMIUM ENGINE: XAUUSD ANALYSIS** 📊\n\n"
                f"**Bias:** {result['bias']}\n"
                f"**Score:** {result['score']}\n\n"
                f"💰 **Gold (XAU):** ${result['xau']:,.2f}\n"
                f"📉 **GLD Proxy:** ${result['gld']:,.2f}\n\n"
                f"🔍 **Core Drivers:**\n{reasons_bullet}\n\n"
                f"⏰ **NY Time:** {ny_time_str} ({ny_date_str})\n"
                f"🏛️ **COMEX Session:** {is_open_status}"
            )
            
            await event.reply(response_message)
            print("🚀 Successfully sent automated XAUUSD analysis reply.")
            return

        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', None) or str(event.chat_id)
        except:
            chat_title = str(event.chat_id)

        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', None) or getattr(sender, 'title', None) or "Unknown"
        except Exception:
            sender_name = chat_title

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
        
        if FIREBASE_URL:
            threading.Thread(target=push, args=(payload,), daemon=True).start()

    except Exception as e:
        print(f"❌ Handler crashed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    if not API_ID or not API_HASH or not SESSION:
        print("❌ Telegram client cannot start due to missing environment variables on Render.")
        return

    await client.start()
    me = await client.get_me()
    print(f"🔥 Engine LIVE as {me.first_name} - @{me.username}")
    print(f"🔥 Listening for triggers (`XAUUSD`) & syncing regular items...")
    
    # Launch background scheduler task concurrently
    asyncio.create_task(scheduled_macro_notifier(client, engine))
    
    count = 0
    async for d in client.iter_dialogs(limit=10):
        print(f"  Joined: {d.name} - {d.id} | Group:{d.is_group} Channel:{d.is_channel}")
        count += 1
    print(f"Total checked {count} dialogs")
    
    await client.run_until_disconnected()


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
 
