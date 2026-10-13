#include <iostream>

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
