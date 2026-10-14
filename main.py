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

class TrendDetector:
    def __init__(self): self.reset()
    def reset(self):
        self.last_swing_high = 0.0; self.prev_swing_high = 0.0
        self.last_swing_low = 0.0; self.prev_swing_low = 0.0
        self.extreme_val = 0.0; self.phase = 0
        self.has_sh = False; self.has_sl = False; self.current_trend = "SIDEWAYS"
    def update(self, price: float):
        if price <= 0: return self.current_trend
        if self.phase == 0:
            self.extreme_val = price; self.last_swing_low = price
            self.last_swing_high = price; self.phase = 1; return self.current_trend
        if self.phase == 1:
            if price > self.extreme_val: self.extreme_val = price; self.last_swing_high = price
            elif price < self.extreme_val:
                self.prev_swing_high = self.last_swing_high; self.last_swing_high = self.extreme_val
                self.has_sh = True; self.extreme_val = price; self.last_swing_low = price; self.phase = 2
        elif self.phase == 2:
            if price < self.extreme_val: self.extreme_val = price; self.last_swing_low = price
            elif price > self.extreme_val:
                self.prev_swing_low = self.last_swing_low; self.last_swing_low = self.extreme_val
                self.has_sl = True; self.extreme_val = price; self.last_swing_high = price; self.phase = 1
                if self.has_sh and self.has_sl:
                    hh = self.last_swing_high > self.prev_swing_high; hl = self.last_swing_low > self.prev_swing_low
                    lh = self.last_swing_high < self.prev_swing_high; ll = self.last_swing_low < self.prev_swing_low
                    if hh and hl: self.current_trend = "UPTREND"
                    elif lh and ll: self.current_trend = "DOWNTREND"
                    else: self.current_trend = "SIDEWAYS"
        return self.current_trend

class TrendBrain:
    def __init__(self):
        self.ema20 = EMA(20); self.ema100 = EMA(100)
        self.trend_detector = TrendDetector()
        self.prev_ema100 = 0.0; self.has_prev = False; self.EPSILON = 1e-7
    def update(self, price: float):
        ema20_val = self.ema20.update(price); ema100_val = self.ema100.update(price)
        structure = self.trend_detector.update(price)
        if not self.ema100.is_ready() or not self.ema20.is_ready():
            return {"bias":f"ACCUMULATING {self.ema100.count}/100","price":price,"ema20":ema20_val,"ema100":ema100_val,
                    "structure":structure,"q1":"Need 100 candles","q2":"Need 100","q3":"Need 100","q4":"Need 100",
                    "sh":self.trend_detector.last_swing_high,"sl":self.trend_detector.last_swing_low,"ready":False}
        if price > ema100_val: q1 = f"ABOVE EMA100 Bulls"
        elif price < ema100_val: q1 = f"BELOW EMA100 Bears"
        else: q1 = "EQUAL"
        if ema20_val > ema100_val: q2 = "EMA20 ABOVE UP"
        elif ema20_val < ema100_val: q2 = "EMA20 BELOW DOWN"
        else: q2 = "EQUAL"
        if not self.has_prev:
            q3 = "Init..."; self.prev_ema100 = ema100_val; self.has_prev = True
        else:
            diff = ema100_val - self.prev_ema100
            if diff > self.EPSILON: q3 = "EMA100 UP 📈"
            elif diff < -self.EPSILON: q3 = "EMA100 DOWN 📉"
            else: q3 = "FLAT"
            self.prev_ema100 = ema100_val
        if structure == "UPTREND": q4 = "UPTREND HH+HL"
        elif structure == "DOWNTREND": q4 = "DOWNTREND LH+LL"
        else: q4 = "SIDEWAYS"
        ema_bull = (price > ema100_val) and (ema20_val > ema100_val)
        ema_bear = (price < ema100_val) and (ema20_val < ema100_val)
        if ema_bull and structure == "UPTREND": bias = "ULTRA_BULLISH"
        elif ema_bear and structure == "DOWNTREND": bias = "ULTRA_BEARISH"
        elif ema_bull: bias = "STRONG_BULLISH"
        elif ema_bear: bias = "STRONG_BEARISH"
        elif price > ema100_val: bias = "BULLISH"
        elif price < ema100_val: bias = "BEARISH"
        else: bias = "SIDEWAYS_CONSOLIDATION"
        return {"bias":bias,"price":price,"ema20":ema20_val,"ema100":ema100_val,
                "structure":structure,"q1":q1,"q2":q2,"q3":q3,"q4":q4,
                "sh":self.trend_detector.last_swing_high,"sl":self.trend_detector.last_swing_low,"ready":True}

# ================== 20 CANDLES TEST + ERROR TRACKER ==================
async def fetch_20_candles_tracker():
    tracker = []
    tracker.append("🔍 STARTING 20 CANDLES TEST")
    
    # METHOD 1: Official deriv-api lib
    try:
        from deriv_api import DerivAPI
        tracker.append("✅ deriv-api lib FOUND")
        
        for app_id in ["1089", "111111"]:
            try:
                tracker.append(f"⏳ TRY app_id={app_id} with 20 candles...")
                api = DerivAPI(app_id=app_id)
                
                # This is exact format from Deriv docs
                res = await api.ticks_history({
                    "ticks_history": "R_75",
                    "adjust_start_time": 1,
                    "count": 20,
                    "end": "latest",
                    "style": "candles",
                    "granularity": 60
                })
                
                tracker.append(f"📥 RAW DERIV RESPONSE app_id {app_id}: {json.dumps(res)[:1000]}")
                
                if "error" in res:
                    tracker.append(f"❌ DERIV ERROR app_id {app_id}: {res['error']}")
                    continue
                
                candles = res.get("candles", [])
                tracker.append(f"✅ Got {len(candles)} candles from app_id {app_id}")
                
                if candles:
                    prices = [float(c["close"]) for c in candles]
                    tracker.append(f"💰 PRICES: {prices[:3]}... to {prices[-1]}")
                    await api.disconnect()
                    return prices, "\n".join(tracker)
                
                await api.disconnect()
                
            except Exception as e:
                tracker.append(f"💥 EXCEPTION app_id {app_id}: {type(e).__name__}: {str(e)[:500]}")
                continue
                
    except ImportError as e:
        tracker.append(f"❌ deriv-api NOT INSTALLED: {e} -> add deriv-api to requirements.txt")
    except Exception as e:
        tracker.append(f"💥 DerivAPI CRITICAL: {type(e).__name__}: {e}")

    # METHOD 2: Raw websockets with Origin header (fixes 520)
    tracker.append("⏳ TRYING raw WS fallback with Origin header...")
    try:
        import websockets
        uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
        tracker.append(f"🔗 Connecting to {uri}")
        
        async with websockets.connect(
            uri,
            extra_headers={"Origin": "https://deriv.com", "User-Agent": "Mozilla/5.0"},
            ping_interval=None,
            close_timeout=10
        ) as ws:
            req = {"ticks_history": "R_75", "count": 20, "end": "latest", "style": "candles", "granularity": 60}
            tracker.append(f"📤 SENDING: {json.dumps(req)}")
            await ws.send(json.dumps(req))
            
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            tracker.append(f"📥 RAW WS RESPONSE: {raw[:1500]}")
            
            data = json.loads(raw)
            if "error" in data:
                tracker.append(f"❌ DERIV WS ERROR: {data['error']}")
            elif "candles" in data:
                candles = data["candles"]
                tracker.append(f"✅ WS Got {len(candles)} candles")
                prices = [float(c["close"]) for c in candles]
                return prices, "\n".join(tracker)
            else:
                tracker.append(f"❓ Unknown WS format: {list(data.keys())}")
                
    except Exception as e:
        tracker.append(f"💥 Raw WS FAILED: {type(e).__name__}: {str(e)[:800]}")

    # METHOD 3: Try binaryws endpoint
    tracker.append("⏳ TRYING binaryws.com endpoint...")
    try:
        import websockets
        uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
        async with websockets.connect(uri, ping_interval=None) as ws:
            req = {"ticks_history": "R_75", "count": 20, "end": "latest", "style": "candles", "granularity": 60}
            await ws.send(json.dumps(req))
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            tracker.append(f"📥 binaryws RAW: {raw[:1500]}")
            data = json.loads(raw)
            if "candles" in data and len(data["candles"]) >= 10:
                prices = [float(c["close"]) for c in data["candles"]]
                return prices, "\n".join(tracker)
    except Exception as e:
        tracker.append(f"💥 binaryws FAILED: {type(e).__name__}: {e}")

    tracker.append("❌ ALL METHODS FAILED - 0 candles")
    return [], "\n".join(tracker)

# ================== FLASK ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 20 CANDLES TEST LIVE 🔥"

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
    low = text.lower()
    if low.startswith("/v75") or low == "v75":
        await event.reply("⏳ TESTING 20 CANDLES - tracking errors...")
        try:
            prices, tracker_log = await fetch_20_candles_tracker()
            
            # SEND TRACKER TO TELEGRAM
            tracker_msg = f"🔍 **DERIV TRACKER LOG (20 candles test):**\n\n{tracker_log[:3500]}"
            await event.reply(tracker_msg)
            
            if len(prices) < 10:
                await event.reply(f"❌ FAILED - got {len(prices)} candles. See tracker above for Deriv's exact error.")
                return

            # If we got 20, show brain analysis (will be accumulating but shows it works)
            brain = TrendBrain()
            result = None
            for p in prices:
                result = brain.update(p)

            msg = (
                f"📊 **V75 TEST - 20 CANDLES SUCCESS!** 📊\n\n"
                f"Got: {len(prices)} candles\n"
                f"Last price: {result['price']:.2f}\n"
                f"Prices: {', '.join([f'{p:.2f}' for p in prices[-5:]])}\n\n"
                f"Bias: {result['bias']}\n"
                f"EMA20: {result['ema20']:.2f} (needs 20)\n"
                f"EMA100: {result['ema100']:.2f} (needs 100)\n"
                f"Note: 20 candles not enough for ULTRA signal, need 100+. But connection WORKS! ✅\n\n"
                f"Now change count to 1000 for full analysis."
            )
            await event.reply(msg)
            
        except Exception as e:
            logger.exception(e)
            await event.reply(f"💥 CRITICAL ERROR: {type(e).__name__}: {e}\n\nTracker:\n{tracker_log[:2000] if 'tracker_log' in locals() else 'no tracker'}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 V75 20 CANDLES TEST BOT LIVE as {me.first_name}")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
