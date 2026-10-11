# === GRAMIUM MATH BRAIN - PURE CALCULATOR ===
# Version: 1.0 GOD - 0 heavy libs, 0 RAM waste, 100% speed
# Author: Gramiun Engine 🔥

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

    # Advanced: Parse "5 + 5" or "10 * 2.5" from telegram text
    def parse_and_calc(self, text: str) -> Union[float, None]:
        try:
            text = text.strip().lower().replace('x', '*')
            for op in ['**', '+', '-', '*', '/', '%', '^']:
                if f" {op} " in f" {text} " or op in text:
                    # Handle calc like "5+5", "5 + 5", "calc 5 * 5"
                    clean = text.replace('calc', '').strip()
                    parts = None
                    if op in clean:
                        # split by op safely
                        idx = clean.find(op)
                        left = clean[:idx].strip()
                        right = clean[idx+len(op):].strip()
                        if left.replace('.','',1).lstrip('-').isdigit() and right.replace('.','',1).lstrip('-').isdigit():
                            return self.calc(float(left), op, float(right))
            return None
        except:
            return None

# Singleton - One brain for whole engine
BRAIN = MathBrain()
