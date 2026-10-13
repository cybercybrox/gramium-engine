import os
import threading
import asyncio
import logging
import json
from datetime import datetime
import websockets
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

# ================== C++ BRAIN PORTED TO PYTHON ==================
class EMA:
    def __init__(self, period):
        self.period = period
        self.multiplier = 2.0 / (period + 1.0)
        self.current_ema = 0.0
        self.count = 0
        self.sum = 0.0
        self.initialized = False
    def reset(self):
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
    def get_value(self): return self.current_ema

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
    def reset(self):
        self.ema20.reset(); self.ema100.reset(); self.trend_detector.reset()
        self.prev_ema100 = 0.0; self.has_prev = False
    def update(self, price: float):
        ema20_val = self.ema20.update(price); ema100_val = self.ema100.update(price)
        structure = self.trend_detector.update(price)
        if not self.ema100.is_ready() or not self.ema20.is_ready():
            return {"bias":"ACCUMULATING","price":price,"ema20":ema20_val,"ema100":ema100_val,
                    "structure":structure,"q1":"Accumulating...","q2":"Accumulating...","q3":"Accumulating...","q4":"Accumulating...",
                    "sh":self.trend_detector.last_swing_high,"sl":self.trend_detector.last_swing_low}
        if price > ema100_val: q1 = f"Price ABOVE EMA100 Bulls ({price:.2f}>{ema100_val:.2f})"
        elif price < ema100_val: q1 = f"Price BELOW EMA100 Bears ({price:.2f}<{ema100_val:.2f})"
        else: q1 = "Price EQUAL EMA100"
        if ema20_val > ema100_val: q2 = "EMA20 ABOVE EMA100 (UP strong)"
        elif ema20_val < ema100_val: q2 = "EMA20 BELOW EMA100 (DOWN strong)"
        else: q2 = "EMA20 EQUAL EMA100"
        if not self.has_prev:
            q3 = "Initializing slope..."; self.prev_ema100 = ema100_val; self.has_prev = True
        else:
            diff = ema100_val - self.prev_ema100
            if diff > self.EPSILON: q3 = "EMA100 UP 📈"
            elif diff < -self.EPSILON: q3 = "EMA100 DOWN 📉"
            else: q3 = "EMA100 FLAT 😴"
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

# ================== DERIV FIXED FETCH - FROM DEVS PORTAL ==================
async def fetch_deriv_v75_candles(days=7):
    """
    Deriv API docs: https://api.deriv.com/api-explorer
    ticks_history with granularity returns candles
    MAX count is 5000 per call - we use 5000 = ~3.5 days of 1min, enough for EMA100
    For full 7 days we loop 2 calls if needed
    """
    uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    all_prices = []

    try:
        async with websockets.connect(uri, ping_interval=20) as ws:
            # We need 7 days but API max 5000, so do 2 batches
            # Batch 1: latest 5000 candles
            # Batch 2: 5000 before that

            # Request 1 - latest
            req1 = {
                "ticks_history": "R_75",
                "adjust_start_time": 1,
                "count": 5000,
                "end": "latest",
                "granularity": 60,
                "style": "candles"
            }
            logger.info(f"Deriv Req1: {req1}")
            await ws.send(json.dumps(req1))
            resp1 = await ws.recv()
            data1 = json.loads(resp1)
            logger.info(f"Deriv Resp1 keys: {data1.keys()}")

            if "error" in data1:
                logger.error(f"Deriv Error: {data1['error']}")
                return []

            candles1 = data1.get("candles", [])
            prices1 = [float(c["close"]) for c in candles1 if "close" in c]
            logger.info(f"Got {len(prices1)} candles batch1")

            if len(prices1) > 0 and days > 4:
                # Request 2 - older batch
                # Use end time = first candle epoch of batch1
                first_epoch = candles1[0]["epoch"] if candles1 else None
                if first_epoch:
                    req2 = {
                        "ticks_history": "R_75",
                        "adjust_start_time": 1,
                        "count": 5000,
                        "end": first_epoch,
                        "granularity": 60,
                        "style": "candles"
                    }
                    await ws.send(json.dumps(req2))
                    resp2 = await ws.recv()
                    data2 = json.loads(resp2)
                    candles2 = data2.get("candles", [])
                    prices2 = [float(c["close"]) for c in candles2 if "close" in c]
                    logger.info(f"Got {len(prices2)} candles batch2")
                    all_prices = prices2 + prices1
                else:
                    all_prices = prices1
            else:
                all_prices = prices1

            logger.info(f"TOTAL FETCHED: {len(all_prices)} R_75 closes")
            return all_prices

    except Exception as e:
        logger.exception(f"Deriv fetch failed: {e}")
        return []

# ================== FLASK ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 ULTRA BRAIN LIVE - FIXED 🔥"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ================== TELEGRAM ==================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")
print(f"ENV CHECK: API_ID={bool(API_ID)} HASH={bool(API_HASH)} SESSION={bool(SESSION)}")

tg_client = TelegramClient(StringSession(SESSION), API_ID, API_HASH, loop=loop)

def format_bias_emoji(bias):
    m = {
        "ULTRA_BULLISH": "🟢🟢🟢 ULTRA_BULLISH 🚀🚀🚀",
        "STRONG_BULLISH": "🟢🟢 STRONG_BULLISH 🚀",
        "BULLISH": "🟢 BULLISH",
        "ULTRA_BEARISH": "🔴🔴🔴 ULTRA_BEARISH 💀💀💀",
        "STRONG_BEARISH": "🔴🔴 STRONG_BEARISH 💀",
        "BEARISH": "🔴 BEARISH",
        "SIDEWAYS_CONSOLIDATION": "🟡 SIDEWAYS 😴",
        "ACCUMULATING": "⏳ ACCUMULATING..."
    }
    return m.get(bias, bias)

@tg_client.on(events.NewMessage)
async def handler(event):
    text = (event.text or "").strip()
    if not text: return
    low = text.lower()

    if low.startswith("/v75") or low == "v75":
        await event.reply("⏳ Fetching V75 from Deriv (fixed, 5000 candles) 🔍")
        try:
            prices = await fetch_deriv_v75_candles(days=7)
            if len(prices) < 110:
                await event.reply(f"❌ Still low data: got {len(prices)}. Raw check logs. Trying fallback ticks...")
                # Fallback: try ticks history without candles style (tick by tick)
                uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
                try:
                    async with websockets.connect(uri) as ws:
                        req = {"ticks_history": "R_75", "count": 5000, "end": "latest", "style": "ticks"}
                        await ws.send(json.dumps(req))
                        resp = await ws.recv()
                        data = json.loads(resp)
                        history = data.get("history", {})
                        ticks = history.get("prices", []) if isinstance(history, dict) else data.get("prices", [])
                        prices = [float(p) for p in ticks]
                        logger.info(f"Fallback ticks got {len(prices)}")
                except Exception as e2:
                    logger.error(f"Fallback failed {e2}")

            if len(prices) < 110:
                await event.reply(f"❌ Deriv still returned {len(prices)}. Check logs on Render dashboard. Will try again later.")
                return

            brain = TrendBrain()
            result = None
            for p in prices:
                result = brain.update(p)

            bias_emoji = format_bias_emoji(result["bias"])
            msg = (
                f"📊 **V75 ULTRA BRAIN (FIXED)** 📊\n\n"
                f"**Symbol:** R_75 (Volatility 75)\n"
                f"**Candles:** {len(prices)} x 1-min closes\n"
                f"**Current:** {result['price']:.2f}\n\n"
                f"🔥 **BIAS: {bias_emoji}**\n\n"
                f"📈 EMA20: {result['ema20']:.2f}\n"
                f"📉 EMA100: {result['ema100']:.2f}\n"
                f"🏔️ Structure: {result['structure']}\n"
                f"🔝 Swing High: {result['sh']:.2f}\n"
                f"🔻 Swing Low: {result['sl']:.2f}\n\n"
                f"🧠 Q1: {result['q1']}\n"
                f"🧠 Q2: {result['q2']}\n"
                f"🧠 Q3: {result['q3']}\n"
                f"🧠 Q4: {result['q4']}\n\n"
            )
            if "ULTRA_BULLISH" in result["bias"]:
                msg += "→ 🟢🟢🟢 BUY pullback to EMA20, SL below swing low 🎯🚀"
            elif "ULTRA_BEARISH" in result["bias"]:
                msg += "→ 🔴🔴🔴 SELL pullback to EMA20, SL above swing high 🎯💀"
            elif "STRONG_BULLISH" in result["bias"]:
                msg += "→ Cautious BUY, waiting for HH+HL"
            elif "STRONG_BEARISH" in result["bias"]:
                msg += "→ Cautious SELL, waiting for LH+LL"
            else:
                msg += "→ SIDEWAYS - No trade 🟡"

            await event.reply(msg)
        except Exception as e:
            logger.exception(e)
            await event.reply(f"❌ Error: {e}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 V75 BOT LIVE as {me.first_name} - @{me.username}")
    print("🔥 Type /V75 to trigger")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
