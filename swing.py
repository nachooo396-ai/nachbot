"""
Simulador de estrategias de varios días o semanas, con velas diarias desde 2016.

- Señal con el cierre de un día, orden en la apertura del día siguiente.
- Acciones fraccionadas (el bróker real también las permite), comisiones IBKR Fixed por orden
  y deslizamiento de 0,05 % por lado.
- Precios ajustados por dividendos y splits.

Uso: python swing.py   (necesita ALPACA_KEY / ALPACA_SECRET). Escribe SWING.md.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

import bot

ETFS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD"]
STOCKS = ("AAPL MSFT AMZN GOOGL META NVDA AMD TSLA INTC F GM AAL DAL UAL CCL BAC C WFC T VZ PFE KO PEP "
          "WMT DIS PYPL BABA JPM XOM CVX HD MCD NKE COST ORCL CSCO QCOM TXN MU ADBE CRM NFLX SBUX").split()
START, SPLIT = "2016-01-01", "2023-01-01"   # 2016-2022 = 1ª parte, 2023-hoy = 2ª parte (comprobación)
SLIPPAGE = 0.0005


def daily(broker, symbols):
    out: dict[str, list] = {}
    for i in range(0, len(symbols), 25):
        chunk, token = symbols[i:i + 25], None
        while True:
            p = {"symbols": ",".join(chunk), "timeframe": "1Day", "start": START, "feed": "sip",
                 "adjustment": "all", "limit": 10000}
            if token:
                p["page_token"] = token
            d = broker._req("GET", f"{bot.DATA_URL}/v2/stocks/bars", params=p)
            for s, rows in (d.get("bars") or {}).items():
                out.setdefault(s, []).extend(rows)
            token = d.get("next_page_token")
            if not token:
                break
    frames = {}
    for s, rows in out.items():
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["t"]).dt.tz_convert(bot.NY).dt.date
        frames[s] = df[["o", "h", "l", "c"]].rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
    opens = pd.DataFrame({s: f["open"] for s, f in frames.items()}).sort_index()
    closes = pd.DataFrame({s: f["close"] for s, f in frames.items()}).sort_index()
    return opens, closes


# ---------------------------------------------------------------- estrategias: devuelven pesos objetivo
def trend_spy(closes, day_i, held):
    c = closes["SPY"]
    if day_i < 200:
        return {}
    return {"SPY": 1.0} if c.iloc[day_i] > c.iloc[day_i - 199:day_i + 1].mean() else {}


def make_rotation(top=2, lookback=126):
    def rotation(closes, day_i, held):
        dates = closes.index
        # solo el último día de cada mes; el resto del mes se mantiene la cartera
        if day_i + 1 < len(dates) and dates[day_i + 1].month == dates[day_i].month:
            return None
        if day_i < lookback:
            return {}
        cols = [s for s in ETFS if s in closes]
        mom = closes[cols].iloc[day_i] / closes[cols].iloc[day_i - lookback] - 1
        picks = [s for s in mom.dropna().sort_values(ascending=False).index[:top] if mom[s] > 0]
        return {s: 1 / top for s in picks}
    return rotation


def make_breakout(slots=3, enter=55, leave=20):
    cache = {}

    def breakout(closes, day_i, held):
        if id(closes) not in cache:
            cols = [c for c in STOCKS if c in closes]
            c = closes[cols]
            cache.clear()
            cache[id(closes)] = (c, c.shift(1).rolling(enter, min_periods=enter).max(),
                                 c.shift(1).rolling(leave, min_periods=leave).min(),
                                 c.rolling(200, min_periods=200).mean(), c / c.shift(126) - 1)
        c, hi, lo, sma, mom = cache[id(closes)]
        if day_i < 200:
            return {}
        row, hi_r, lo_r, sma_r, mom_r = c.iloc[day_i], hi.iloc[day_i], lo.iloc[day_i], sma.iloc[day_i], mom.iloc[day_i]
        keep = {s for s in held if not (row[s] < lo_r[s])}
        ok = (row > hi_r) & (row > sma_r)
        cands = mom_r[ok & ~row.index.isin(list(keep))].dropna().sort_values(ascending=False)
        new = list(cands.index[: max(slots - len(keep), 0)])
        return {s: 1 / slots for s in list(keep) + new}
    return breakout


STRATEGIES = {
    "Comprar y mantener SPY (referencia)": lambda c, i, h: {"SPY": 1.0},
    "T1 Tendencia: SPY solo si está sobre su media de 200 días": trend_spy,
    "T2 Rotación mensual: los 2 ETF con más subida en 6 meses (si suben)": make_rotation(),
    "T3 Rupturas: acciones en máximos de 55 días, venta en mínimo de 20 días (máx. 3)": make_breakout(),
}


def simulate(strategy, opens, closes, cfg, start_cash):
    dates = closes.index
    cash, qty = start_cash, {}
    equity, trades, fees = [], 0, 0.0
    target = None
    for i, d in enumerate(dates):
        # 1) ejecutar en la apertura la cartera decidida ayer
        if target is not None:
            value = cash + sum(q * opens.at[d, s] for s, q in qty.items() if not np.isnan(opens.at[d, s]))
            for s in list(qty):                       # ventas
                if s not in target:
                    px = opens.at[d, s] * (1 - SLIPPAGE)
                    if np.isnan(px):
                        continue
                    fee = bot.commission(cfg, qty[s], px)
                    cash += qty.pop(s) * px - fee
                    fees += fee; trades += 1
            for s, w in target.items():               # compras (sin reajustar lo que ya se tiene)
                if s in qty:
                    continue
                px = opens.at[d, s] * (1 + SLIPPAGE)
                if np.isnan(px):
                    continue
                amount = min(value * w, cash)
                if amount < 20:
                    continue
                fee = bot.commission(cfg, amount / px, px)
                qty[s] = (amount - fee) / px
                cash -= amount
                fees += fee; trades += 1
            target = None
        # 2) valor al cierre y nueva señal
        eq = cash + sum(q * closes.at[d, s] for s, q in qty.items() if not np.isnan(closes.at[d, s]))
        equity.append(eq)
        t = strategy(closes, i, set(qty))
        if t is not None and set(t) != set(qty):
            target = t
    return pd.Series(equity, index=dates), trades, fees


def metrics(eq: pd.Series, start, end):
    e = eq[(eq.index >= start) & (eq.index < end)]
    years = (pd.Timestamp(e.index[-1]) - pd.Timestamp(e.index[0])).days / 365.25
    total = e.iloc[-1] / e.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else 0
    dd = (e / e.cummax() - 1).min()
    return total * 100, cagr * 100, dd * 100


def main():
    cfg = bot.Config()
    opens, closes = daily(bot.Alpaca(cfg), ETFS + STOCKS)
    split = datetime.fromisoformat(SPLIT).date()
    end = closes.index[-1]
    lines = [f"# Estrategias de varios días ({closes.index[0]} a {end})", "",
             f"Capital inicial {cfg.budget:.0f} $, comisiones IBKR Fixed, deslizamiento 0,05 % por lado, "
             "acciones fraccionadas, precios con dividendos.", "",
             "| Estrategia | Periodo | Resultado total % | Al año % | Peor caída % | Operaciones | Comisiones $ |",
             "|---|---|---|---|---|---|---|"]
    for name, strat in STRATEGIES.items():
        eq, n, fees = simulate(strat, opens, closes, cfg, cfg.budget)
        for label, a, b in (("Todo", closes.index[0], end + pd.Timedelta(days=1)),
                            ("2016-2022", closes.index[0], split), ("2023-hoy", split, end + pd.Timedelta(days=1))):
            tot, cagr, dd = metrics(eq, a, b)
            lines.append(f"| {name} | {label} | {tot:+.1f} | {cagr:+.1f} | {dd:.1f} | "
                         + (f"{n} | {fees:.0f} |" if label == "Todo" else " | |"))
        print(name, f"{eq.iloc[-1]:.0f} $", n, "ops", flush=True)
    lines += ["", "Nota: la lista de acciones de T3 es la de hoy (empresas que han sobrevivido), lo que "
              "favorece algo a esa estrategia."]
    with open("SWING.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
