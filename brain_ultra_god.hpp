class EMA100 {
private:
    static constexpr int PERIOD = 100;
    double multiplier;
    double current_ema;
    int count;
    double sum;
    bool initialized;

public:
    EMA100() 
        : multiplier(2.0 / (PERIOD + 1.0)), 
          current_ema(0.0), 
          count(0), 
          sum(0.0), 
          initialized(false) {}

    void reset() {
        current_ema = 0.0;
        count = 0;
        sum = 0.0;
        initialized = false;
    }

    inline double update(double price) {
        if (price <= 0.0) {
            return current_ema;
        }

        if (!initialized) {
            count++;
            sum += price;
            if (count == PERIOD) {
                current_ema = sum / PERIOD;
                initialized = true;
            } else {
                current_ema = sum / count; 
            }
            return current_ema;
        }

        current_ema = (price * multiplier) + (current_ema * (1.0 - multiplier));
        return current_ema;
    }

    inline bool isReady() const {
        return initialized;
    }

    inline double getValue() const {
        return current_ema;
    }
};

class EMA20 {
private:
    static constexpr int PERIOD = 20;
    double multiplier;
    double current_ema;
    int count;
    double sum;
    bool initialized;

public:
    EMA20() 
        : multiplier(2.0 / (PERIOD + 1.0)), 
          current_ema(0.0), 
          count(0), 
          sum(0.0), 
          initialized(false) {}

    void reset() {
        current_ema = 0.0;
        count = 0;
        sum = 0.0;
        initialized = false;
    }

    inline double update(double price) {
        if (price <= 0.0) {
            return current_ema;
        }

        if (!initialized) {
            count++;
            sum += price;
            if (count == PERIOD) {
                current_ema = sum / PERIOD;
                initialized = true;
            } else {
                current_ema = sum / count; 
            }
            return current_ema;
        }

        current_ema = (price * multiplier) + (current_ema * (1.0 - multiplier));
        return current_ema;
    }

    inline bool isReady() const {
        return initialized;
    }

    inline double getValue() const {
        return current_ema;
    }
};

enum class MarketTrend {
    SIDEWAYS,
    UPTREND,
    DOWNTREND
};

class TrendDetector {
private:
    double last_swing_high;
    double prev_swing_high;
    double last_swing_low;
    double prev_swing_low;
    double extreme_val;
    int phase;
    bool has_sh;
    bool has_sl;
    MarketTrend current_trend;

public:
    TrendDetector() 
        : last_swing_high(0.0), 
          prev_swing_high(0.0), 
          last_swing_low(0.0), 
          prev_swing_low(0.0), 
          extreme_val(0.0), 
          phase(0), 
          has_sh(false), 
          has_sl(false), 
          current_trend(MarketTrend::SIDEWAYS) {}

    void reset() {
        last_swing_high = 0.0;
        prev_swing_high = 0.0;
        last_swing_low = 0.0;
        prev_swing_low = 0.0;
        extreme_val = 0.0;
        phase = 0;
        has_sh = false;
        has_sl = false;
        current_trend = MarketTrend::SIDEWAYS;
    }

    inline MarketTrend update(double price) {
        if (price <= 0.0) {
            return current_trend;
        }

        if (phase == 0) {
            extreme_val = price;
            last_swing_low = price;
            last_swing_high = price;
            phase = 1;
            return current_trend;
        }

        if (phase == 1) {
            if (price > extreme_val) {
                extreme_val = price;
                last_swing_high = price;
            } else if (price < extreme_val) {
                prev_swing_high = last_swing_high;
                last_swing_high = extreme_val;
                has_sh = true;
                extreme_val = price;
                last_swing_low = price;
                phase = 2;
            }
        } else if (phase == 2) {
            if (price < extreme_val) {
                extreme_val = price;
                last_swing_low = price;
            } else if (price > extreme_val) {
                prev_swing_low = last_swing_low;
                last_swing_low = extreme_val;
                has_sl = true;
                extreme_val = price;
                last_swing_high = price;
                phase = 1;

                if (has_sh && has_sl) {
                    bool hh = last_swing_high > prev_swing_high;
                    bool hl = last_swing_low > prev_swing_low;
                    bool lh = last_swing_high < prev_swing_high;
                    bool ll = last_swing_low < prev_swing_low;

                    if (hh && hl) {
                        current_trend = MarketTrend::UPTREND;
                    } else if (lh && ll) {
                        current_trend = MarketTrend::DOWNTREND;
                    } else {
                        current_trend = MarketTrend::SIDEWAYS;
                    }
                }
            }
        }

        return current_trend;
    }

    inline MarketTrend getTrend() const {
        return current_trend;
    }

    inline double getLastSwingHigh() const {
        return last_swing_high;
    }

    inline double getLastSwingLow() const {
        return last_swing_low;
    }
};

enum class TrendBias {
    ULTRA_BULLISH,
    STRONG_BULLISH,
    BULLISH,
    ULTRA_BEARISH,
    STRONG_BEARISH,
    BEARISH,
    SIDEWAYS_CONSOLIDATION
};

struct TrendAnalysis {
    TrendBias bias;
    MarketTrend structure_trend;
    const char* q1_price_vs_slow; 
    const char* q2_emas_relation; 
    const char* q3_slow_slope;
    const char* q4_market_structure;    
    double current_price;
    double ema20_val;
    double ema100_val;
    double last_swing_high;
    double last_swing_low;
};

class TrendBrain {
private:
    EMA20 ema20;
    EMA100 ema100;
    TrendDetector trend_detector;
    double prev_ema100;
    bool has_previous_ema100;
    static constexpr double EPSILON = 1e-7;

public:
    TrendBrain() : prev_ema100(0.0), has_previous_ema100(false) {}

    void reset() {
        ema20.reset();
        ema100.reset();
        trend_detector.reset();
        prev_ema100 = 0.0;
        has_previous_ema100 = false;
    }

    inline TrendAnalysis update(double price) {
        TrendAnalysis analysis;
        analysis.current_price = price;

        ema20.update(price);
        double current_ema100 = ema100.update(price);
        MarketTrend structure = trend_detector.update(price);

        analysis.ema20_val = ema20.getValue();
        analysis.ema100_val = current_ema100;
        analysis.structure_trend = structure;
        analysis.last_swing_high = trend_detector.getLastSwingHigh();
        analysis.last_swing_low = trend_detector.getLastSwingLow();

        if (!ema100.isReady() || !ema20.isReady()) {
            analysis.bias = TrendBias::SIDEWAYS_CONSOLIDATION;
            analysis.q1_price_vs_slow = "Accumulating data...";
            analysis.q2_emas_relation = "Accumulating data...";
            analysis.q3_slow_slope = "Accumulating data...";
            analysis.q4_market_structure = "Accumulating data...";
            return analysis;
        }

        if (price > current_ema100) {
            analysis.q1_price_vs_slow = "Price ABOVE EMA100 (Bulls in control)";
        } else if (price < current_ema100) {
            analysis.q1_price_vs_slow = "Price BELOW EMA100 (Bears in control)";
        } else {
            analysis.q1_price_vs_slow = "Price EQUAL to EMA100";
        }

        if (analysis.ema20_val > current_ema100) {
            analysis.q2_emas_relation = "EMA20 ABOVE EMA100 (Trend is UP and strong)";
        } else if (analysis.ema20_val < current_ema100) {
            analysis.q2_emas_relation = "EMA20 BELOW EMA100 (Trend is DOWN and strong)";
        } else {
            analysis.q2_emas_relation = "EMA20 EQUAL to EMA100";
        }

        if (!has_previous_ema100) {
            prev_ema100 = current_ema100;
            has_previous_ema100 = true;
            analysis.q3_slow_slope = "Initializing slope...";
        } else {
            double diff = current_ema100 - prev_ema100;
            if (diff > EPSILON) {
                analysis.q3_slow_slope = "EMA100 pointing UP (Trend up)";
            } else if (diff < -EPSILON) {
                analysis.q3_slow_slope = "EMA100 pointing DOWN (Trend down)";
            } else {
                analysis.q3_slow_slope = "EMA100 is FLAT";
            }
            prev_ema100 = current_ema100;
        }

        if (structure == MarketTrend::UPTREND) {
            analysis.q4_market_structure = "UPTREND confirmed (HH + HL structure)";
        } else if (structure == MarketTrend::DOWNTREND) {
            analysis.q4_market_structure = "DOWNTREND confirmed (LH + LL structure)";
        } else {
            analysis.q4_market_structure = "SIDEWAYS structure (Consolidation)";
        }

        bool ema_bullish = (price > current_ema100) && (analysis.ema20_val > current_ema100);
        bool ema_bearish = (price < current_ema100) && (analysis.ema20_val < current_ema100);

        if (ema_bullish && structure == MarketTrend::UPTREND) {
            analysis.bias = TrendBias::ULTRA_BULLISH;
        } else if (ema_bearish && structure == MarketTrend::DOWNTREND) {
            analysis.bias = TrendBias::ULTRA_BEARISH;
        } else if (ema_bullish) {
            analysis.bias = TrendBias::STRONG_BULLISH;
        } else if (ema_bearish) {
            analysis.bias = TrendBias::STRONG_BEARISH;
        } else if (price > current_ema100) {
            analysis.bias = TrendBias::BULLISH;
        } else if (price < current_ema100) {
            analysis.bias = TrendBias::BEARISH;
        } else {
            analysis.bias = TrendBias::SIDEWAYS_CONSOLIDATION;
        }

        return analysis;
    }
};
