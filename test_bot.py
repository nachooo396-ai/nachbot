"""Pruebas sin conexión: python3 test_bot.py"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import bot

NOW = datetime(2026, 11, 12, 17, 0, tzinfo=timezone.utc)          # 12:00 en Nueva York
OPEN = datetime(2026, 11, 12, 14, 30, tzinfo=timezone.utc)
CLOSE = datetime(2026, 11, 12, 21, 0, tzinfo=timezone.utc)


def bars_with_cross():
    """Bajada suave y luego subida: fuerza un cruce EMA9 > EMA21 en la última vela."""
    n = 30
    times = [OPEN + timedelta(minutes=5 * i) for i in range(n)]
    base = [100 - 0.04 * i + (0.15 if i % 2 else -0.15) for i in range(24)]
    up = [base[-1] + 0.08 * k + (0.12 if k % 2 else -0.12) for k in range(1, 7)]
    prices = base + up
    df = pd.DataFrame({"time": times, "close": prices})
    df["open"] = df["close"]; df["high"] = df["close"] + .05; df["low"] = df["close"] - .05
    df["volume"] = 1000
    return df


class Fake:
    def __init__(self, equity=100000, last_equity=100000, is_open=True, df=None):
        self.equity, self.last_equity, self.is_open = equity, last_equity, is_open
        self.df = df if df is not None else bars_with_cross()
        self.orders, self.closed = [], False

    def clock(self): return {"is_open": self.is_open, "next_close": CLOSE.isoformat()}
    def account(self): return {"equity": str(self.equity), "last_equity": str(self.last_equity)}
    def session_open(self, nc): return OPEN
    def positions(self): return []
    def open_orders(self): return []
    def orders_since(self, s): return []
    def close_all(self): self.closed = True
    def bars(self, sym, start): return self.df.copy()
    def buy_bracket(self, *a): self.orders.append(a)


cfg = bot.Config()
cfg.budget, cfg.start_equity = 1000, 100000

# Capital: las ganancias se apartan, las pérdidas reducen el capital
assert bot.trading_capital(cfg, 100150) == (1000, 150)
assert bot.trading_capital(cfg, 99900) == (900, 0)

# Tamaño: 1000 $ / 3 huecos = 333 $ -> 3 acciones a 100 $
assert bot.position_size(cfg, 1000, 100) == 3

# Señal detectada
assert bot.entry_signal(bars_with_cross()[bars_with_cross()["time"] <= NOW - timedelta(minutes=5)])

# Mercado cerrado
f = Fake(is_open=False); assert "cerrado" in bot.run(f, cfg, NOW)[-1] and not f.orders

# Compra con señal (máximo 3 posiciones)
f = Fake(); log = bot.run(f, cfg, NOW)
assert len(f.orders) == 3, log
sym, qty, tp, sl = f.orders[0]
assert qty == 3 and tp > sl

# Stop del día: pierde 30 $ (3 % de 1000)
f = Fake(equity=99970, last_equity=100000); log = bot.run(f, cfg, NOW)
assert f.closed and not f.orders and "STOP DEL DÍA" in log[-1]

# Interruptor de apagado: pierde 250 $ (25 %) en total
f = Fake(equity=99750, last_equity=99750); log = bot.run(f, cfg, NOW)
assert f.closed and "APAGADO" in log[-1]

# Cierre antes del final de sesión
f = Fake(); log = bot.run(f, cfg, CLOSE - timedelta(minutes=5))
assert f.closed and "Fin de sesión" in log[-1]

# No entra al principio de la sesión
f = Fake(); bot.run(f, cfg, OPEN + timedelta(minutes=10)); assert not f.orders

print("Todas las pruebas OK")
