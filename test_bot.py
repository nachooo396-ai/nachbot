"""Pruebas sin conexión: python3 test_bot.py"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import bot
import numpy as np

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
        self.orders, self.closed, self.filled = [], False, []

    def clock(self): return {"is_open": self.is_open, "next_close": CLOSE.isoformat()}
    def account(self): return {"equity": str(self.equity), "last_equity": str(self.last_equity)}
    def session_open(self, nc): return OPEN
    def positions(self): return []
    def open_orders(self): return []
    def orders_since(self, s): return []
    def filled_orders_since(self, s): return self.filled
    def close_all(self): self.closed = True
    def bars(self, sym, start): return self.df.copy()
    def most_actives(self, top): return ["XYZ", "ABC", "SPY"]
    def bars_multi(self, syms, start): return {s: self.df.copy() for s in syms}
    def buy_bracket(self, *a): self.orders.append(a)


cfg = bot.Config()
cfg.budget, cfg.start_equity = 1000, 100000

# Capital: las ganancias se apartan, las pérdidas reducen el capital
assert bot.trading_capital(cfg, 100150) == (1000, 150)
assert bot.trading_capital(cfg, 99900) == (900, 0)

# Tamaño: 1000 $ / 2 huecos = 500 $ -> 5 acciones a 100 $
assert bot.position_size(cfg, 1000, 100) == 5

# Comisiones IBKR Fixed: mínimo 1 $, 0,005 $/acción, máximo 1 %
assert bot.commission(cfg, 5, 100) == 1.0
assert bot.commission(cfg, 1000, 50) == 5.0
assert abs(bot.commission(cfg, 10, 5) - 0.5) < 1e-9          # tope del 1 %
# 500 $ con objetivo +1,5 % = 7,5 $; comisiones 2 $ = 27 % -> no compensa. 1000 $ -> 2 $ de 15 $ = 13 % -> sí
assert not bot.worth_it(cfg, 5, 100) and bot.worth_it(cfg, 10, 100)

# Señal detectada
assert bot.entry_signal(bars_with_cross(), OPEN)
# Con historial de días anteriores también da señal al principio de la sesión
hist = bars_with_cross(); hist["time"] = hist["time"] - timedelta(minutes=5 * 25)
assert bot.entry_signal(hist, OPEN)

# Mercado cerrado
f = Fake(is_open=False); assert "cerrado" in bot.run(f, cfg, NOW)[-1] and not f.orders

# Con 1000 $ y 2 huecos (500 $), las comisiones no compensan -> no compra
f = Fake(); log = bot.run(f, cfg, NOW)
assert not f.orders and any("comisiones" in l for l in log), log

# Con 2300 $ (1150 $ por hueco) sí compra, máximo 2 posiciones
cfg2 = bot.Config(); cfg2.budget, cfg2.start_equity = 2300, 100000
f = Fake(); log = bot.run(f, cfg2, NOW)
assert len(f.orders) == 2, log
sym, qty, tp, sl = f.orders[0]
assert qty == 11 and tp > sl

# Las comisiones se descuentan del resultado: 2 órdenes ejecutadas de 10 acc. a 100 $ = 2 $
f = Fake(equity=100010); f.filled = [{"filled_qty": "10", "filled_avg_price": "100", "filled_at": NOW.isoformat()}] * 2
log = bot.run(f, cfg, NOW)
assert "Ganancias apartadas para retirar: 8.00" in log[1] and "+8.00" in log[1], log

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

# ---------------------------------------------------------------- estrategia de rupturas (varios días)
import swing
days = [d.date() for d in pd.bdate_range("2025-09-01", "2026-11-12")]   # incluye hoy (se ignora)
wave = 100 + 3 * np.sin(np.arange(len(days)) / 7)
base = pd.DataFrame({s: wave for s in swing.STOCKS}, index=days)
base.loc[days[-2], "AAPL"] = 150      # ayer: máximo de 55 días y sobre su media de 200 -> compra
base.loc[days[-2], "NVDA"] = 50       # ayer: por debajo del mínimo de 20 días -> venta
base.loc[days[-1], :] = 999           # la vela de hoy (sin cerrar) no debe usarse
class SwingFake(Fake):
    def __init__(self, positions=(), orders=()):
        super().__init__(); self.pos, self.oo, self.bought, self.sold = list(positions), list(orders), [], []
    def positions(self): return self.pos
    def open_orders(self): return self.oo
    def daily_closes(self, syms, start): return base.copy()
    def buy_notional(self, sym, amt): self.bought.append((sym, amt))
    def sell_all(self, sym): self.sold.append(sym)
nv = {"symbol": "NVDA", "unrealized_pl": "-5", "market_value": "380", "unrealized_plpc": "-0.01"}
ko = {"symbol": "KO", "unrealized_pl": "3", "market_value": "390", "unrealized_plpc": "0.01"}
cfg3 = bot.Config(); cfg3.budget, cfg3.start_equity = 1150, 100000
f = SwingFake(positions=[nv, ko]); log = bot.run_swing(f, cfg3, NOW)
assert f.sold == ["NVDA"] and [b[0] for b in f.bought] == ["AAPL"], log
assert 370 < f.bought[0][1] < 384, f.bought          # 1150 / 3 menos comisión
# Repetir la pasada con la compra pendiente no duplica órdenes
f2 = SwingFake(positions=[ko], orders=[{"symbol": "AAPL", "side": "buy", "order_class": "simple"}])
bot.run_swing(f2, cfg3, NOW); assert not f2.bought and not f2.sold
# Paso desde intradía: órdenes bracket abiertas -> cierra todo primero
f3 = SwingFake(orders=[{"symbol": "AAL", "side": "sell", "order_class": "bracket"}])
log = bot.run_swing(f3, cfg3, NOW); assert f3.closed and not f3.bought, log
# Posición fuera del universo (p. ej. TLT de antes) -> se vende
f4 = SwingFake(positions=[{"symbol": "TLT", "unrealized_pl": "0", "market_value": "300", "unrealized_plpc": "0"}])
bot.run_swing(f4, cfg3, NOW); assert "TLT" in f4.sold
print("Pruebas de rupturas OK")
