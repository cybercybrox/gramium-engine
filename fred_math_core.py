# === GRAMIUM MATH BRAIN - PURE CALCULATOR ===
# Version: 1.2 FINAL - Supports.Calc + clean integer output
# Author: Gramiun Engine 🔥

from typing import List, Union

Number = Union[int, float]

class MathBrain:
    __slots__ = ()

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

    def pretty(self, value: float) -> Union[int, float]:
        # 10.0 -> 10, 10.5 -> 10.5
        if value is None:
            return 0
        if float(value).is_integer():
            return int(value)
        return float(value)

    def parse_and_calc(self, text: str) -> Union[int, float, None]:
        try:
            t = text.strip().lower()

            # Remove.calc /calc calc
            if t.startswith('.calc'):
                t = t[5:].strip()
            elif t.startswith('/calc'):
                t = t[5:].strip()
            elif t.startswith('calc'):
                t = t[4:].strip()

            t = t.lstrip('.').lstrip('/').lstrip(':').strip()
            t = t.replace('x', '*')

            if not t:
                return None

            for op in ['**', '+', '-', '*', '/', '%', '^']:
                if op in t:
                    parts = t.split(op)
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()
                        try:
                            a = float(left)
                            b = float(right)
                            res = self.calc(a, op, b)
                            return self.pretty(res)
                        except:
                            continue
            return None
        except:
            return None

BRAIN = MathBrain()
