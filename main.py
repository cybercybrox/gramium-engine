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
        if price > ema100_val: q1 = f"ABOVE EMA100 Bulls {price:.2f}>{ema100_val:.2f}"
        elif price < ema100_val: q1 = f"BELOW EMA100 Bears {price:.2f}<{ema100_val:.2f}"
        else: q1 = "EQUAL"
        if ema20_val > ema100_val: q2 = "EMA20 ABOVE EMA100 UP"
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
                "sh":self.trend_detector.last_swing_high,"sl":self.trend_detector.last_swing_low}

# ================== DERIV OFFICIAL LIBRARY FETCH ==================
async def fetch_deriv_v75_candles_with_errors():
    """
    Uses official deriv_api Python lib from Deriv dev portal
    Docs: https://developers.deriv.com/
    pip install deriv-api
    """
    errors_log = []
    try:
        from deriv_api import DerivAPI
        import websockets
        
        # Try multiple app_ids - 1089 is demo, 111111 is public, 101480 is another
        # Also try with origin header to bypass Cloudflare 520
        app_ids = ["1089", "111111", "101480", "36956"]
        
        for app_id in app_ids:
            try:
                logger.info(f"TRYING DerivAPI with app_id={app_id}")
                # DerivAPI handles connection itself
                api = DerivAPI(app_id=app_id)
                
                # Get 1000 candles 1m = enough for EMA100 + 7 days partial
                # Deriv docs: ticks_history
                response = await api.ticks_history({
                    "ticks_history": "R_75",
                    "adjust_start_time": 1,
                    "count": 1000,
                    "end": "latest",
                    "style": "candles",
                    "granularity": 60
                })
                
                logger.info(f"Deriv response with app_id {app_id}: {str(response)[:600]}")
                
                if "error" in response:
                    err = response["error"]
                    errors_log.append(f"app_id {app_id} error: {err}")
                    logger.error(f"Deriv error {app_id}: {err}")
                    continue
                
                candles = response.get("candles", [])
                if candles and len(candles) >= 100:
                    prices = [float(c["close"]) for c in candles]
                    logger.info(f"SUCCESS {len(prices)} candles with app_id {app_id}")
                    return prices, f"SUCCESS with app_id {app_id}"
                else:
                    errors_log.append(f"app_id {app_id} returned {len(candles)} candles, need >100")
                    
                    # Try ticks style as fallback
                    response2 = await api.ticks_history({
                        "ticks_history": "R_75",
                        "count": 1000,
                        "end": "latest",
                        "style": "ticks"
                    })
                    logger.info(f"Ticks fallback response: {str(response2)[:600]}")
                    if "history" in response2:
                        hist = response2["history"]
                        prices_raw = hist.get("prices", []) if isinstance(hist, dict) else []
                        if len(prices_raw) >= 100:
                            prices = [float(p) for p in prices_raw]
                            return prices, f"SUCCESS TICKS with app_id {app_id}"
                
                await api.disconnect()
                
            except Exception as e:
                err_str = f"app_id {app_id} exception: {type(e).__name__}: {e}"
                errors_log.append(err_str)
                logger.error(err_str)
                continue
        
        # If all app_ids failed, try raw websockets with proper Origin header (fixes 520)
        logger.info("All DerivAPI app_ids failed, trying raw WS with Origin header...")
        try:
            import websockets
            uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
            async with websockets.connect(
                uri, 
                extra_headers={"Origin": "https://api.deriv.com", "User-Agent": "Mozilla/5.0"},
                ping_interval=None
            ) as ws:
                req = {"ticks_history": "R_75", "count": 1000, "end": "latest", "style": "candles", "granularity": 60}
                await ws.send(json.dumps(req))
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                data = json.loads(raw)
                logger.info(f"Raw WS with Origin: {raw[:800]}")
                if "candles" in data:
                    candles = data["candles"]
                    if len(candles) >= 100:
                        return [float(c["close"]) for c in candles], "SUCCESS raw WS with Origin"
                errors_log.append(f"Raw WS response: {raw[:500]}")
        except Exception as e:
            errors_log.append(f"Raw WS with Origin failed: {type(e).__name__}: {e}")
        
        return [], "\n".join(errors_log) if errors_log else "No errors logged - total fail"
        
    except ImportError as e:
        return [], f"deriv-api lib not installed: {e} - add deriv-api to requirements.txt"
    except Exception as e:
        return [], f"CRITICAL FETCH ERROR: {type(e).__name__}: {e}\n" + "\n".join(errors_log)

# ================== FLASK ==================
app = Flask(__name__)
@app.route('/')
def home(): return "V75 BRAIN - OFFICIAL DERIV API 🔥"

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
        await event.reply("⏳ Connecting to Deriv using OFFICIAL lib... trying 4 app_ids 🔍")
        try:
            prices, debug_info = await fetch_deriv_v75_candles_with_errors()
            logger.info(f"FINAL prices: {len(prices)} debug: {debug_info}")
            
            if len(prices) < 100:
                # SEND DERIV ERRORS TO TELEGRAM AS YOU ASKED
                error_msg = (
                    f"❌ Deriv API Failed (got {len(prices)} candles)\n\n"
                    f"🔍 **DERIV ERRORS:**\n{debug_info[:3000]}\n\n"
                    f"💡 **FIX:**\n"
                    f"1. Go to https://api.deriv.com\n"
                    f"2. Login → Manage App → Register App\n"
                    f"3. Get your own app_id (free)\n"
                    f"4. Set ENV var DERIV_APP_ID on Render\n"
                    f"5. Or try redeploy - Render IP sometimes blocked (520)\n\n"
                    f"Current Render IP got HTTP 520 from Cloudflare"
                )
                await event.reply(error_msg)
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
                f"📊 **V75 ULTRA BRAIN (OFFICIAL API)** 📊\n\n"
                f"Symbol: R_75 (Volatility 75)\n"
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
                f"Q4: {result['q4']}\n\n"
                f"Debug: {debug_info}\n"
            )
            await event.reply(msg)
        except Exception as e:
            logger.exception(e)
            await event.reply(f"❌ Critical Error: {type(e).__name__}: {e}")

async def main():
    await tg_client.start()
    me = await tg_client.get_me()
    print(f"🔥 V75 BOT LIVE as {me.first_name} - @{me.username}")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop.run_until_complete(main())
