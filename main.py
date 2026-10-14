import os
import threading
import asyncio
import logging
import json
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ================== BRAIN (SAME) ==================
class EMA:
    def __init__(self, period):
        self.period = period
        self.multiplier = 2.0 / (period + 1.0)
        self.current_ema = 0.0; self.count = 0; self.sum = 0.0; self.initialized = False
    def update(self, price: float):
        if price <= 0: return self.current_ema
        if not self.initialized:
            self.count += 1; self.sum += price
            if self.count == self.period:
                self.current_ema = self.sum / self.period; self.initialized = True
            else: self.current_ema = self.sum / self.count
            return self.current_ema
        self.current_ema = (price * self.multiplier) + (self.current_ema * (1.0 - self.multiplier))
        return self.current_ema
    def is_ready(self): return self.initialized

class TrendBrain:
    def __init__(self):
        self.ema20 = EMA(20); self.ema100 = EMA(100)
        self.count = 0
    def update(self, price: float):
        e20 = self.ema20.update(price); e100 = self.ema100.update(price)
        self.count += 1
        ready = self.ema20.is_ready() and self.ema100.is_ready()
        return {"price":price,"ema20":e20,"ema100":e100,"ready":ready,"count":self.count}

# ================== 20 CANDLES WITH TIMEOUTS ==================
async def fetch_20_candles_tracker():
    tracker = []
    tracker.append("🔍 START 20 CANDLES TEST")

    # TRY 1: Raw WS with Origin - NO LIB, fastest
    try:
        import websockets
        tracker.append("⏳ TRY 1: ws.derivws.com + Origin header (10s timeout)")
        uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
        
        async def try_ws(uri_to_try):
            async with websockets.connect(
                uri_to_try,
                additional_headers={"Origin": "https://deriv.com"},
                open_timeout=8,
                close_timeout=5
            ) as ws:
                req = {"ticks_history": "R_75", "count": 20, "end": "latest", "style": "candles", "granularity": 60}
                await ws.send(json.dumps(req))
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                return raw

        try:
            raw = await asyncio.wait_for(try_ws(uri), timeout=12)
            tracker.append(f"📥 RAW: {raw[:1200]}")
            data = json.loads(raw)
            if "candles" in data:
                prices = [float(c["close"]) for c in data["candles"]]
                tracker.append(f"✅ SUCCESS {len(prices)} candles via derivws")
                return prices, "\n".join(tracker)
            if "error" in data:
                tracker.append(f"❌ Deriv ERROR says: {data['error']}")
        except asyncio.TimeoutError:
            tracker.append("⏰ TIMEOUT ws.derivws.com (12s) - IP blocked 520")
        except Exception as e:
            tracker.append(f"💥 TRY1 FAIL: {type(e).__name__}: {str(e)[:500]}")

        # TRY 2: binaryws endpoint
        tracker.append("⏳ TRY 2: ws.binaryws.com (10s timeout)")
        try:
            raw = await asyncio.wait_for(try_ws("wss://ws.binaryws.com/websockets/v3?app_id=1089"), timeout=12)
            tracker.append(f"📥 RAW binaryws: {raw[:1200]}")
            data = json.loads(raw)
            if "candles" in data:
                prices = [float(c["close"]) for c in data["candles"]]
                tracker.append(f"✅ SUCCESS {len(prices)} via binaryws")
                return prices, "\n".join(tracker)
        except asyncio.TimeoutError:
            tracker.append("⏰ TIMEOUT binaryws.com")
        except Exception as e:
            tracker.append(f"💥 TRY2 FAIL: {type(e).__name__}: {e}")

        # TRY 3: python-deriv-api lib with timeout
        tracker.append("⏳ TRY 3: python-deriv-api lib (10s timeout)")
        try:
            from deriv_api import DerivAPI
            async def try_lib():
                api = DerivAPI(app_id="1089")
                res = await api.ticks_history({
                    "ticks_history": "R_75",
                    "count": 20,
                    "end": "latest",
                    "style": "candles",
                    "granularity": 60
                })
                return res
            
            res = await asyncio.wait_for(try_lib(), timeout=12)
            tracker.append(f"📥 LIB RAW: {json.dumps(res)[:1200]}")
            if "candles" in res:
                prices = [float(c["close"]) for c in res["candles"]]
                tracker.append(f"✅ SUCCESS {len(prices)} via lib")
                return prices, "\n".join(tracker)
            if "error" in res:
                tracker.append(f"❌ LIB ERROR: {res['error']}")
        except asyncio.TimeoutError:
            tracker.append("⏰ TIMEOUT python-deriv-api lib")
        except Exception as e:
            tracker.append(f"💥 TRY3 FAIL: {type(e).__name__}: {str(e)[:500]}")

    except Exception as e:
        tracker.append(f"💥 CRITICAL: {type(e).__name__}: {e}")

    tracker.append("❌ ALL 3 METHODS FAILED - Render IP likely blocked by Cloudflare 520")
    tracker.append("💡 SOLUTION: Use proxy or change Render region, or use HTTP API")
    return [], "\n".join(tracker)

# ================== FLASK ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 20 CANDLES TEST 🔥"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ================== TELEGRAM ==================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")

tg_client = TelegramClient(StringSession(SESSION), API_ID, API_HASH, loop=loop)

@tg_client.on(events.NewMessage)
async def handler(event):
    text = (event.text or "").strip()
    if not text: return
    if text.lower().startswith("/v75") or text.lower() == "v75":
        await event.reply("⏳ TESTING 20 CANDLES - 15 sec max...")
        try:
            # FORCE 20 sec total timeout so bot ALWAYS replies
            try:
                prices, tracker_log = await asyncio.wait_for(fetch_20_candles_tracker(), timeout=20)
            except asyncio.TimeoutError:
                tracker_log = "⏰ TOTAL FETCH TIMEOUT 20s - Render IP blocked 520"
                prices = []
            
            # ALWAYS SEND TRACKER FIRST
            await event.reply(f"🔍 **TRACKER LOG:**\n\n{tracker_log[:3500]}")
            
            if len(prices) < 5:
                await event.reply(f"❌ Got {len(prices)} candles. Check tracker above. Deriv blocked Render IP 520.")
                return
            
            brain = TrendBrain()
            result = None
            for p in prices:
                result = brain.update(p)
            
            msg = (
                f"📊 **V75 20 CANDLES - SUCCESS!**\n\n"
                f"Count: {len(prices)}\n"
                f"Last: {result['price']:.2f}\n"
                f"Last 5: {', '.join([f'{p:.2f}' for p in prices[-5:]])}\n\n"
                f"EMA20: {result['ema20']:.2f} ready={brain.ema20.is_ready()}\n"
                f"EMA100: {result['ema100']:.2f} ready={brain.ema100.is_ready()}\n\n"
                f"✅ Connection WORKS! Now we can bump to 1000 candles"
            )
            await event.reply(msg)
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()[:2000]
            await event.reply(f"💥 Handler error: {type(e).__name__}: {e}\n{tb}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 BOT LIVE {me.first_name}")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
