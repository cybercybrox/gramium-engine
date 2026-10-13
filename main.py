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
            return {"bias":"ACCUMULATING","price":price,"ema20":ema20_val,"ema100":ema100_val,
                    "structure":structure,"q1":"Accumulating...","q2":"Accumulating...","q3":"Accumulating...","q4":"Accumulating...",
                    "sh":self.trend_detector.last_swing_high,"sl":self.trend_detector.last_swing_low}
        if price > ema100_val: q1 = f"Price ABOVE EMA100 Bulls ({price:.2f}>{ema100_val:.2f})"
        elif price < ema100_val: q1 = f"Price BELOW EMA100 Bears ({price:.2f}<{ema100_val:.2f})"
        else: q1 = "EQUAL"
        if ema20_val > ema100_val: q2 = "EMA20 ABOVE EMA100 (UP)"
        elif ema20_val < ema100_val: q2 = "EMA20 BELOW EMA100 (DOWN)"
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
                "sh":self.trend_detector.last_swing_high,"sl":self.trend_detector.last_swing_low}

# ================== DERIV FETCH - NEW ROBUST VERSION ==================
async def fetch_deriv_v75_candles():
    # We will try 3 endpoints and 2 methods, with full logging
    endpoints = [
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        "wss://ws.binaryws.com/websockets/v3?app_id=1089",
        "wss://ws.deriv.com/websockets/v3?app_id=1089"
    ]
    
    for uri in endpoints:
        try:
            logger.info(f"TRYING DERIV URI: {uri}")
            import websockets
            # Use new loop for deriv to avoid Telethon loop conflict
            async with websockets.connect(uri, ping_interval=None, close_timeout=10) as ws:
                # Try 1: CANDLES
                req_candles = {
                    "ticks_history": "R_75",
                    "adjust_start_time": 1,
                    "count": 1000,  # reduced to 1000 for test, enough for EMA100
                    "end": "latest",
                    "style": "candles",
                    "granularity": 60
                }
                await ws.send(json.dumps(req_candles))
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(raw)
                
                logger.info(f"RAW RESPONSE from {uri} (first 500 chars): {raw[:500]}")
                
                if "error" in data:
                    logger.error(f"Deriv error on candles: {data['error']}")
                else:
                    candles = data.get("candles", [])
                    if candles and len(candles) > 100:
                        prices = [float(c["close"]) for c in candles]
                        logger.info(f"SUCCESS CANDLES {len(prices)} from {uri}")
                        return prices
                
                # Try 2: TICKS if candles failed
                req_ticks = {
                    "ticks_history": "R_75",
                    "count": 1000,
                    "end": "latest",
                    "style": "ticks"
                }
                await ws.send(json.dumps(req_ticks))
                raw2 = await asyncio.wait_for(ws.recv(), timeout=10)
                data2 = json.loads(raw2)
                logger.info(f"RAW TICKS RESPONSE (first 500): {raw2[:500]}")
                
                if "history" in data2:
                    hist = data2["history"]
                    prices_raw = hist.get("prices", []) if isinstance(hist, dict) else []
                    if len(prices_raw) > 100:
                        prices = [float(p) for p in prices_raw]
                        logger.info(f"SUCCESS TICKS {len(prices)}")
                        return prices
                if "tick" in data2 or "prices" in data2:
                    prices_raw = data2.get("prices", [])
                    if len(prices_raw) > 100:
                        return [float(p) for p in prices_raw]
                        
        except Exception as e:
            logger.error(f"Failed URI {uri}: {e}")
            continue
    
    # LAST RESORT: Try Deriv HTTP API via httpx (no websocket)
    try:
        logger.info("TRYING HTTP FALLBACK...")
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            # Deriv has unofficial charting endpoint, but we can try active_symbols first
            # Actually use binary.com endpoint that returns ticks via HTTP? 
            # We'll fake with synthetic but log it
            logger.warning("HTTP fallback not implemented for Deriv - returning empty")
    except Exception as e:
        logger.error(f"HTTP fallback failed {e}")
    
    return []

# ================== FLASK ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 BRAIN FIXED V3 LIVE 🔥"

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
        await event.reply("⏳ Connecting to Deriv V75... trying 3 servers (check Render logs) 🔍")
        try:
            prices = await fetch_deriv_v75_candles()
            logger.info(f"FINAL prices count: {len(prices)}")
            
            if len(prices) < 110:
                await event.reply(f"❌ Deriv returned {len(prices)} candles. This is Deriv API issue.\n\nLook at Render LOGS - I printed raw response. Screenshot logs and send me.\n\nTrying one more time with minimal request...")
                # One last super minimal request
                try:
                    import websockets
                    async with websockets.connect("wss://ws.derivws.com/websockets/v3?app_id=1089") as ws:
                        await ws.send(json.dumps({"ticks_history": "R_75", "count": 500, "end": "latest", "style": "ticks"}))
                        raw = await ws.recv()
                        await event.reply(f"DEBUG RAW: {raw[:800]}")
                except Exception as e:
                    await event.reply(f"DEBUG ERROR: {e}")
                return

            brain = TrendBrain()
            result = None
            for p in prices:
                result = brain.update(p)

            emoji_map = {
                "ULTRA_BULLISH": "🟢🟢🟢 ULTRA_BULLISH 🚀🚀🚀",
                "STRONG_BULLISH": "🟢🟢 STRONG_BULLISH 🚀",
                "BULLISH": "🟢 BULLISH",
                "ULTRA_BEARISH": "🔴🔴🔴 ULTRA_BEARISH 💀💀💀",
                "STRONG_BEARISH": "🔴🔴 STRONG_BEARISH 💀",
                "BEARISH": "🔴 BEARISH",
                "SIDEWAYS_CONSOLIDATION": "🟡 SIDEWAYS 😴",
                "ACCUMULATING": "⏳ ACCUMULATING..."
            }
            bias_emoji = emoji_map.get(result["bias"], result["bias"])
            
            msg = (
                f"📊 **V75 ULTRA BRAIN FIXED V3** 📊\n\n"
                f"Symbol: R_75\n"
                f"Candles: {len(prices)} x 1m\n"
                f"Price: {result['price']:.2f}\n\n"
                f"🔥 BIAS: {bias_emoji}\n\n"
                f"EMA20: {result['ema20']:.2f}\n"
                f"EMA100: {result['ema100']:.2f}\n"
                f"Structure: {result['structure']}\n"
                f"High: {result['sh']:.2f} Low: {result['sl']:.2f}\n\n"
                f"Q1: {result['q1']}\n"
                f"Q2: {result['q2']}\n"
                f"Q3: {result['q3']}\n"
                f"Q4: {result['q4']}\n"
            )
            await event.reply(msg)
        except Exception as e:
            logger.exception(e)
            await event.reply(f"❌ Error: {e}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 V75 BOT LIVE as {me.first_name} - @{me.username}")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
