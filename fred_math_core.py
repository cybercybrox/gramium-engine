# === GRAMIUM MATH BRAIN - PURE CALCULATOR ===
# Version: 1.1 FIXED - 0 heavy libs, 0 RAM waste, 100% speed
# Author: Gramiun Engine 🔥 - FIXED for /calc command

from typing import List, Union

Number = Union[int, float]

class MathBrain:
    __slots__ = () # Super fast, no __dict__

    def add(self, a: Number, b: Number) -> float:
        return float(a + b)

    def sub(self, a: Number, b: Number) -> float:
        return float(a - b)

    def mul(self, a: Number, b: Number) -> float:
        return float(a * b)

    def div(self, a: Number, b: Number) -> float:
        if b == 0 or b == 0.0:
            return 0.0
        return float(a / b)

    def mod(self, a: Number, b: Number) -> float:
        return float(a % b) if b else 0.0

    def pow(self, a: Number, b: Number) -> float:
        return float(a ** b)

    def calc(self, a: Number, op: str, b: Number) -> float:
        op = op.strip()
        if op == '+': return self.add(a, b)
        if op == '-': return self.sub(a, b)
        if op in ('*', 'x', 'X'): return self.mul(a, b)
        if op == '/': return self.div(a, b)
        if op == '%': return self.mod(a, b)
        if op in ('^', '**'): return self.pow(a, b)
        return 0.0

    def batch(self, numbers: List[Number], op: str = '+') -> float:
        if not numbers:
            return 0.0
        r = float(numbers[0])
        for n in numbers[1:]:
            r = self.calc(r, op, n)
        return r

    def avg(self, numbers: List[Number]) -> float:
        if not numbers:
            return 0.0
        return self.batch(numbers, '+') / len(numbers)

    # FIXED: Parse "/calc 5 + 5" correctly
    def parse_and_calc(self, text: str) -> Union[float, None]:
        try:
            t = text.strip().lower()

            # 1. Remove command prefix cleanly
            if t.startswith('/calc'):
                t = t[5:].strip() # remove /calc
            elif t.startswith('calc'):
                t = t[4:].strip() # remove calc

            # Remove any leftover leading / or :
            t = t.lstrip('/').lstrip(':').strip()
            t = t.replace('x', '*')

            # t is now "5 + 5"
            if not t:
                return None

            for op in ['**', '+', '-', '*', '/', '%', '^']:
                if op in t:
                    parts = t.split(op)
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()
                        # Check if both are numbers
                        try:
                            a = float(left)
                            b = float(right)
                            return self.calc(a, op, b)
                        except:
                            continue
            return None
        except Exception as e:
            print(f"Parse error: {e}")
            return None

# Singleton - One brain for whole engine
BRAIN = MathBrain()
