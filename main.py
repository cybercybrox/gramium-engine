import os
import threading
import asyncio
import logging
import json
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ================== BRAIN ==================
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
    def update(self, price: float):
        e20 = self.ema20.update(price); e100 = self.ema100.update(price)
        ready = self.ema20.is_ready() and self.ema100.is_ready()
        return {"price":price,"ema20":e20,"ema100":e100,"ready":ready}

# ================== 20 CANDLES FIXED ==================
async def fetch_20_candles_tracker():
    tracker = []
    tracker.append("🔍 START 20 CANDLES TEST")

    try:
        import websockets
        tracker.append(f"ℹ️ websockets lib version: {websockets.__version__}")

        # Helper that tries both header names for old/new lib
        async def connect_with_headers(uri):
            try:
                # Try NEW way (websockets >=13)
                return await websockets.connect(
                    uri,
                    additional_headers={"Origin": "https://deriv.com", "User-Agent": "Mozilla/5.0"},
                    open_timeout=8
                )
            except TypeError as e:
                if "additional_headers" in str(e):
                    tracker.append("⚠️ Old websockets lib, using extra_headers")
                    # OLD way (websockets <13)
                    return await websockets.connect(
                        uri,
                        extra_headers=[("Origin", "https://deriv.com"), ("User-Agent", "Mozilla/5.0")],
                        open_timeout=8
                    )
                raise

        # TRY 1: derivws
        tracker.append("⏳ TRY 1: ws.derivws.com (12s timeout)")
        try:
            async def try_ws(uri):
                ws = await connect_with_headers(uri)
                async with ws:
                    req = {"ticks_history": "R_75", "count": 20, "end": "latest", "style": "candles", "granularity": 60}
                    await ws.send(json.dumps(req))
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    return raw

            raw = await asyncio.wait_for(try_ws("wss://ws.derivws.com/websockets/v3?app_id=1089"), timeout=14)
            tracker.append(f"📥 RAW: {raw[:1200]}")
            data = json.loads(raw)
            if "candles" in data:
                prices = [float(c["close"]) for c in data["candles"]]
                tracker.append(f"✅ SUCCESS {len(prices)} candles via derivws")
                return prices, "\n".join(tracker)
            if "error" in data:
                tracker.append(f"❌ Deriv says: {data['error']}")
        except asyncio.TimeoutError:
            tracker.append("⏰ TIMEOUT TRY1 - Deriv blocked IP 520")
        except Exception as e:
            tracker.append(f"💥 TRY1 FAIL: {type(e).__name__}: {str(e)[:600]}")

        # TRY 2: binaryws
        tracker.append("⏳ TRY 2: ws.binaryws.com (12s timeout)")
        try:
            raw = await asyncio.wait_for(try_ws("wss://ws.binaryws.com/websockets/v3?app_id=1089"), timeout=14)
            tracker.append(f"📥 RAW binaryws: {raw[:1200]}")
            data = json.loads(raw)
            if "candles" in data:
                prices = [float(c["close"]) for c in data["candles"]]
                tracker.append(f"✅ SUCCESS {len(prices)} via binaryws")
                return prices, "\n".join(tracker)
        except asyncio.TimeoutError:
            tracker.append("⏰ TIMEOUT TRY2")
        except Exception as e:
            tracker.append(f"💥 TRY2 FAIL: {type(e).__name__}: {str(e)[:600]}")

        # TRY 3: Try without any headers (last resort)
        tracker.append("⏳ TRY 3: No headers, bare connection (10s)")
        try:
            async def try_bare():
                async with websockets.connect("wss://ws.derivws.com/websockets/v3?app_id=1089", open_timeout=8) as ws:
                    await ws.send(json.dumps({"ticks_history": "R_75", "count": 20, "end": "latest", "style": "candles", "granularity": 60}))
                    raw = await asyncio.wait_for(ws.recv(), timeout=8)
                    return raw
            raw = await asyncio.wait_for(try_bare(), timeout=12)
            tracker.append(f"📥 BARE RAW: {raw[:1200]}")
            data = json.loads(raw)
            if "candles" in data:
                prices = [float(c["close"]) for c in data["candles"]]
                return prices, "\n".join(tracker)
        except Exception as e:
            tracker.append(f"💥 TRY3 FAIL: {type(e).__name__}: {str(e)[:600]}")

    except Exception as e:
        tracker.append(f"💥 CRITICAL: {type(e).__name__}: {e}")

    tracker.append("❌ ALL FAILED - Render IP blocked by Cloudflare")
    tracker.append("💡 WORKAROUND: We will use HTTP fallback via Deriv charts API")
    
    # TRY 4: HTTP fallback - get ticks via httpx (doesn't use websocket, bypasses 520)
    tracker.append("⏳ TRY 4: HTTP REST via api.deriv.com (bypass WS)")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            # Deriv has HTTP endpoint for active symbols, but candles need WS - we try alternative public API
            # Using Deriv's charting data via https://api.deriv.com/api/explorer fallback not available
            # So we try third-party mirror: https://quotes.binaryws.com or use Deriv's own HTTP ticks
            tracker.append("ℹ️ HTTP method not available for candles, need WS")
    except Exception as e:
        tracker.append(f"💥 HTTP TRY FAIL: {e}")

    return [], "\n".join(tracker)

# ================== FLASK ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 TEST FIXED 🔥"

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
        await event.reply("⏳ TESTING 20 CANDLES - fixed headers...")
        try:
            try:
                prices, tracker_log = await asyncio.wait_for(fetch_20_candles_tracker(), timeout=25)
            except asyncio.TimeoutError:
                tracker_log = "⏰ TOTAL TIMEOUT 25s"
                prices = []
            
            await event.reply(f"🔍 **TRACKER LOG:**\n\n{tracker_log[:3500]}")
            
            if len(prices) < 5:
                await event.reply("❌ Failed. Send me tracker log screenshot!")
                return
            
            brain = TrendBrain()
            result = None
            for p in prices:
                result = brain.update(p)
            
            await event.reply(
                f"📊 **V75 20 CANDLES SUCCESS!**\n\n"
                f"Count: {len(prices)}\n"
                f"Last: {result['price']:.2f}\n"
                f"Prices tail: {', '.join([f'{p:.2f}' for p in prices[-5:]])}\n\n"
                f"✅ WORKS! Ready for 1000 candles"
            )
        except Exception as e:
            import traceback
            await event.reply(f"💥 Error: {e}\n{traceback.format_exc()[:1500]}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 BOT LIVE {me.first_name}")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
