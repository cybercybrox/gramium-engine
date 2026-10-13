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
