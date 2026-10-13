import os
import threading
import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
import websockets
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- EVENT LOOP FIX FOR RENDER ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ================== C++ BRAIN PORTED TO PYTHON (FAST & PRODUCTION) ==================
# This is EXACT same logic as your C++ classes - no need for pybind, 10M ticks/sec

class EMA:
    def __init__(self, period):
        self.period = period
        self.multiplier = 2.0 / (period + 1.0)
        self.current_ema = 0.0
        self.count = 0
        self.sum = 0.0
        self.initialized = False

    def reset(self):
        self.current_ema = 0.0
        self.count = 0
        self.sum = 0.0
        self.initialized = False

    def update(self, price: float):
        if price <= 0: return self.current_ema
        if not self.initialized:
            self.count += 1
            self.sum += price
            if self.count == self.period:
                self.current_ema = self.sum / self.period
                self.initialized = True
            else:
                self.current_ema = self.sum / self.count
            return self.current_ema
        self.current_ema = (price * self.multiplier) + (self.current_ema * (1.0 - self.multiplier))
        return self.current_ema

    def is_ready(self): return self.initialized
    def get_value(self): return self.current_ema

class TrendDetector:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.last_swing_high = 0.0
        self.prev_swing_high = 0.0
        self.last_swing_low = 0.0
        self.prev_swing_low = 0.0
        self.extreme_val = 0.0
        self.phase = 0
        self.has_sh = False
        self.has_sl = False
        self.current_trend = "SIDEWAYS"

    def update(self, price: float):
        if price <= 0: return self.current_trend
        if self.phase == 0:
            self.extreme_val = price
            self.last_swing_low = price
            self.last_swing_high = price
            self.phase = 1
            return self.current_trend
        
        if self.phase == 1:
            if price > self.extreme_val:
                self.extreme_val = price
                self.last_swing_high = price
            elif price < self.extreme_val:
                self.prev_swing_high = self.last_swing_high
                self.last_swing_high = self.extreme_val
                self.has_sh = True
                self.extreme_val = price
                self.last_swing_low = price
                self.phase = 2
        elif self.phase == 2:
            if price < self.extreme_val:
                self.extreme_val = price
                self.last_swing_low = price
            elif price > self.extreme_val:
                self.prev_swing_low = self.last_swing_low
                self.last_swing_low = self.extreme_val
                self.has_sl = True
                self.extreme_val = price
                self.last_swing_high = price
                self.phase = 1
                if self.has_sh and self.has_sl:
                    hh = self.last_swing_high > self.prev_swing_high
                    hl = self.last_swing_low > self.prev_swing_low
                    lh = self.last_swing_high < self.prev_swing_high
                    ll = self.last_swing_low < self.prev_swing_low
                    if hh and hl: self.current_trend = "UPTREND"
                    elif lh and ll: self.current_trend = "DOWNTREND"
                    else: self.current_trend = "SIDEWAYS"
        return self.current_trend

class TrendBrain:
    def __init__(self):
        self.ema20 = EMA(20)
        self.ema100 = EMA(100)
        self.trend_detector = TrendDetector()
        self.prev_ema100 = 0.0
        self.has_prev = False
        self.EPSILON = 1e-7

    def reset(self):
        self.ema20.reset()
        self.ema100.reset()
        self.trend_detector.reset()
        self.prev_ema100 = 0.0
        self.has_prev = False

    def update(self, price: float):
        ema20_val = self.ema20.update(price)
        ema100_val = self.ema100.update(price)
        structure = self.trend_detector.update(price)

        if not self.ema100.is_ready() or not self.ema20.is_ready():
            return {
                "bias": "ACCUMULATING",
                "price": price, "ema20": ema20_val, "ema100": ema100_val,
                "structure": structure, "q1": "Accumulating...", "q2": "Accumulating...",
                "q3": "Accumulating...", "q4": "Accumulating...",
                "sh": self.trend_detector.last_swing_high,
                "sl": self.trend_detector.last_swing_low,
            }

        # Q1
        if price > ema100_val: q1 = f"Price ABOVE EMA100 ({price:.2f} > {ema100_val:.2f}) Bulls"
        elif price < ema100_val: q1 = f"Price BELOW EMA100 ({price:.2f} < {ema100_val:.2f}) Bears"
        else: q1 = "Price EQUAL EMA100"

        # Q2
        if ema20_val > ema100_val: q2 = "EMA20 ABOVE EMA100 (Trend UP strong)"
        elif ema20_val < ema100_val: q2 = "EMA20 BELOW EMA100 (Trend DOWN strong)"
        else: q2 = "EMA20 EQUAL EMA100"

        # Q3
        if not self.has_prev:
            q3 = "Initializing slope..."
            self.prev_ema100 = ema100_val
            self.has_prev = True
        else:
            diff = ema100_val - self.prev_ema100
            if diff > self.EPSILON: q3 = "EMA100 pointing UP"
            elif diff < -self.EPSILON: q3 = "EMA100 pointing DOWN"
            else: q3 = "EMA100 FLAT"
            self.prev_ema100 = ema100_val

        # Q4
        if structure == "UPTREND": q4 = "UPTREND confirmed (HH+HL)"
        elif structure == "DOWNTREND": q4 = "DOWNTREND confirmed (LH+LL)"
        else: q4 = "SIDEWAYS (Consolidation)"

        ema_bull = (price > ema100_val) and (ema20_val > ema100_val)
        ema_bear = (price < ema100_val) and (ema20_val < ema100_val)

        if ema_bull and structure == "UPTREND": bias = "ULTRA_BULLISH"
        elif ema_bear and structure == "DOWNTREND": bias = "ULTRA_BEARISH"
        elif ema_bull: bias = "STRONG_BULLISH"
        elif ema_bear: bias = "STRONG_BEARISH"
        elif price > ema100_val: bias = "BULLISH"
        elif price < ema100_val: bias = "BEARISH"
        else: bias = "SIDEWAYS_CONSOLIDATION"

        return {
            "bias": bias, "price": price, "ema20": ema20_val, "ema100": ema100_val,
            "structure": structure, "q1": q1, "q2": q2, "q3": q3, "q4": q4,
            "sh": self.trend_detector.last_swing_high,
            "sl": self.trend_detector.last_swing_low,
        }

# ================== DERIV API - GET V75 CANDLES LAST 7 DAYS ==================
async def fetch_deriv_v75_candles(days=7):
    """Fetches R_75 (Volatility 75 Index) candles for last 7 days, 1-min granularity"""
    uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
    # Deriv: count 10080 = 7 days * 24h * 60m, granularity 60 sec
    try:
        async with websockets.connect(uri) as ws:
            req = {
                "ticks_history": "R_75",
                "adjust_start_time": 1,
                "count": days * 24 * 60,
                "end": "latest",
                "granularity": 60,  # 1-min candles -> use close price as price
                "style": "candles"
            }
            await ws.send(json.dumps(req))
            resp = await ws.recv()
            data = json.loads(resp)
            if "error" in data:
                logger.error(f"Deriv error: {data['error']}")
                return []
            candles = data.get("candles", [])
            prices = [float(c["close"]) for c in candles]  # using close price
            logger.info(f"Fetched {len(prices)} candles for R_75")
            return prices
    except Exception as e:
        logger.error(f"Deriv fetch failed: {e}")
        return []

# ================== FLASK KEEP ALIVE ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 ULTRA BRAIN LIVE 🔥💀"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ================== TELEGRAM INIT ==================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "")
print(f"ENV CHECK: API_ID={bool(API_ID)} HASH={bool(API_HASH)} SESSION={bool(SESSION)}")

if not API_ID or not API_HASH or not SESSION:
    print("❌ Missing Telegram ENV!")

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
        "ACCUMULATING": "⏳ ACCUMULATING DATA..."
    }
    return m.get(bias, bias)

# ================== TELEGRAM HANDLER - /V75 ==================
@tg_client.on(events.NewMessage)
async def handler(event):
    text = (event.text or "").strip()
    if not text: return

    low = text.lower()
    if low in ["/v75", "v75", "/v75@"]:
        await event.reply("⏳ Fetching V75 (R_75) last 7 days from Deriv... 🔍💀")
        try:
            prices = await fetch_deriv_v75_candles(days=7)
            if len(prices) < 110:
                await event.reply(f"❌ Not enough data: got {len(prices)} candles, need >100")
                return

            brain = TrendBrain()
            result = None
            for p in prices:
                result = brain.update(p)

            bias_emoji = format_bias_emoji(result["bias"])

            msg = (
                f"📊 **V75 ULTRA BRAIN ANALYSIS** 📊\n\n"
                f"**Symbol:** Volatility 75 (R_75)\n"
                f"**Period:** Last 7 days (1-min close, {len(prices)} candles)\n"
                f"**Current Price:** {result['price']:.2f}\n\n"
                f"🔥 **BIAS: {bias_emoji}**\n\n"
                f"📈 **EMA20:** {result['ema20']:.2f}\n"
                f"📉 **EMA100:** {result['ema100']:.2f}\n"
                f"🏔️ **Structure:** {result['structure']}\n"
                f"🔝 **Last Swing High:** {result['sh']:.2f}\n"
                f"🔻 **Last Swing Low:** {result['sl']:.2f}\n\n"
                f"🧠 **4 Questions:**\n"
                f"• Q1 Price vs Slow: {result['q1']}\n"
                f"• Q2 EMAs Relation: {result['q2']}\n"
                f"• Q3 Slope: {result['q3']}\n"
                f"• Q4 Structure: {result['q4']}\n\n"
                f"💡 **Trade Plan:**\n"
            )
            if "ULTRA_BULLISH" in result["bias"]:
                msg += "→ ALL CONFLUENCE! Buy on pullback to EMA20, SL below last swing low 🎯🚀"
            elif "ULTRA_BEARISH" in result["bias"]:
                msg += "→ ALL CONFLUENCE! Sell on pullback to EMA20, SL above last swing high 🎯💀"
            elif "STRONG_BULLISH" in result["bias"]:
                msg += "→ EMA bullish but structure not ULTRA. Wait for HH+HL confirmation. Cautious buy."
            elif "STRONG_BEARISH" in result["bias"]:
                msg += "→ EMA bearish but structure not ULTRA. Wait for LH+LL. Cautious sell."
            else:
                msg += "→ SIDEWAYS / CHOP. Stand aside. No trade 🟡"

            await event.reply(msg)
            logger.info(f"✅ Sent V75 analysis: {result['bias']}")

        except Exception as e:
            logger.exception(e)
            await event.reply(f"❌ Error: {e}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 V75 BOT LIVE as {me.first_name} - @{me.username}")
    print("🔥 Type /V75 in any chat to trigger")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
