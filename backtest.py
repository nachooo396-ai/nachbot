"""
Simulador (backtest) de NachBot con precios reales de 5 minutos.

Reproduce las reglas del bot: entrada en la apertura de la vela siguiente a la señal, stop y objetivo,
máximo de posiciones, presupuesto, comisiones de Interactive Brokers, límite de pérdida diaria y cierre
antes del final de la sesión. Si en una misma vela se tocan stop y objetivo, cuenta el stop (pesimista).

Uso:  python backtest.py [días]     (necesita ALPACA_KEY / ALPACA_SECRET)
Escribe BACKTEST.md con la comparación de estrategias.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import bot

UNIVERSE = ("SPY QQQ IWM DIA XLF XLE XLK TLT HYG GLD SLV AAPL MSFT AMZN GOOGL META NVDA AMD TSLA INTC "
            "F GM AAL DAL UAL CCL NCLH PLTR SOFI NIO BAC C WFC T VZ PFE KO PEP WMT DIS UBER SNAP RIVN "
            "LCID MARA RIOT COIN PYPL BABA").split()
SLIPPAGE = 0.0002  # 0,02 % peor precio en cada entrada y salida


# ---------------------------------------------------------------- datos
def fetch(broker: bot.Alpaca, days: int):
    end = datetime.now(timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=int(days * 1.5) + 7)
    cal = broker._req("GET", f"{broker.cfg.base_url}/v2/calendar",
                      params={"start": start.date().isoformat(), "end": end.date().isoformat()})
    sessions = []
    for d in cal:
        o = datetime.fromisoformat(f"{d['date']}T{d['open']}:00").replace(tzinfo=bot.NY)
        c = datetime.fromisoformat(f"{d['date']}T{d['close']}:00").replace(tzinfo=bot.NY)
        if c < end:
            sessions.append((pd.Timestamp(o).tz_convert("UTC"), pd.Timestamp(c).tz_convert("UTC")))
    sessions = sessions[-days:]
    first = sessions[0][0] - timedelta(days=4)
    data = {}
    for feed in ("sip", "iex"):
        try:
            data = bars(broker, UNIVERSE, first, end, feed)
            break
        except RuntimeError as e:
            print(f"feed {feed} no disponible: {e}", flush=True)
    return sessions, data


def bars(broker, symbols, start, end, feed):
    out: dict[str, list] = {}
    for i in range(0, len(symbols), 25):
        chunk, token = symbols[i:i + 25], None
        while True:
            params = {"symbols": ",".join(chunk), "timeframe": "5Min", "start": start.isoformat(),
                      "end": end.isoformat(), "feed": feed, "adjustment": "split", "limit": 10000}
            if token:
                params["page_token"] = token
            d = broker._req("GET", f"{bot.DATA_URL}/v2/stocks/bars", params=params)
            for s, rows in (d.get("bars") or {}).items():
                out.setdefault(s, []).extend(rows)
            token = d.get("next_page_token")
            if not token:
                break
    res = {}
    for s, rows in out.items():
        df = pd.DataFrame(rows).rename(columns={"t": "time", "o": "open", "h": "high", "l": "low",
                                                "c": "close", "v": "volume"})
        df["time"] = pd.to_datetime(df["time"], utc=True)
        res[s] = df.sort_values("time").set_index("time")[["open", "high", "low", "close", "volume"]]
    return res


def regular_hours(df: pd.DataFrame, sessions) -> pd.DataFrame:
    mask = np.zeros(len(df), bool)
    idx = df.index
    for o, c in sessions:
        mask |= (idx >= o) & (idx < c)
    return df[mask]


# ---------------------------------------------------------------- indicadores y estrategias
def indicators(df: pd.DataFrame, sessions) -> pd.DataFrame:
    df = df.copy()
    df["day"] = df.index.tz_convert(bot.NY).date
    df["ema9"], df["ema21"] = bot.ema(df["close"], 9), bot.ema(df["close"], 21)
    df["rsi"] = bot.rsi(df["close"])
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    tp = (df["high"] + df["low"] + df["close"]) / 3
    g = df.groupby("day")
    df["vwap"] = (tp * df["volume"]).groupby(df["day"]).cumsum() / df["volume"].groupby(df["day"]).cumsum().replace(0, np.nan)
    df["bar_n"] = g.cumcount()
    df["vol_avg"] = df["volume"].rolling(78, min_periods=20).mean()
    first6 = df[df["bar_n"] < 6]
    orh, orl = first6.groupby("day")["high"].max(), first6.groupby("day")["low"].min()
    df["or_high"], df["or_low"] = df["day"].map(orh), df["day"].map(orl)
    df["cross_up"] = (df["ema9"] > df["ema21"]) & (df["ema9"].shift() <= df["ema21"].shift())
    return df


@dataclass
class Strategy:
    name: str
    desc: str
    market_filter: bool = False
    kind: str = "ema"          # "ema" (cruce de medias) | "orb" (ruptura del rango de apertura)
    stop: str = "pct"          # "pct" (0,75 %) | "atr" (1,5 x ATR)
    rr: float = 2.0            # objetivo = rr x distancia del stop

    def signals(self, df: pd.DataFrame, spy: pd.DataFrame | None):
        if self.kind == "ema":
            sig = df["cross_up"] & (df["close"] > df["vwap"]) & df["rsi"].between(50, 70)
        elif self.kind == "mr":  # reversión a la media dentro del día
            sig = ((df["bar_n"] >= 3) & (df["close"] < df["vwap"] - 2 * df["atr"]) & (df["rsi"] < 25))
        else:  # ORB
            sig = ((df["bar_n"] >= 6) & (df["close"] > df["or_high"]) & (df["close"].shift() <= df["or_high"])
                   & (df["volume"] > 1.2 * df["vol_avg"]))
        if self.market_filter and spy is not None:
            ok = ((spy["close"] > spy["vwap"]) & (spy["ema9"] > spy["ema21"])).reindex(df.index).fillna(False)
            sig &= ok
        if self.stop == "pct":
            dist = df["close"] * 0.0075
        else:
            dist = 1.5 * df["atr"]
        if self.kind == "orb":
            dist = np.maximum(dist, df["close"] - (df["or_high"] + df["or_low"]) / 2)
        return sig.fillna(False), dist


STRATEGIES = [
    Strategy("A_actual", "Actual: cruce EMA 9/21 + VWAP + RSI 50-70, stop 0,75 %, objetivo 1,5 %"),
    Strategy("B_filtro", "A + solo compra si el mercado (SPY) está alcista", market_filter=True),
    Strategy("C_atr", "B + stop según volatilidad (1,5 x ATR), objetivo 2x el stop", market_filter=True, stop="atr"),
    Strategy("D_orb", "Ruptura del rango de los primeros 30 min con volumen, filtro de mercado",
             market_filter=True, kind="orb", stop="atr"),
    Strategy("E_orb_sin_filtro", "D sin filtro de mercado", kind="orb", stop="atr"),
    Strategy("F_rebote", "Rebote: compra caídas bruscas bajo el VWAP (2 ATR, RSI<25), objetivo 1,5 ATR, stop 1,5 ATR",
             kind="mr", stop="atr", rr=1.0),
    Strategy("G_rebote_filtro", "F solo con el mercado (SPY) alcista", kind="mr", stop="atr", rr=1.0,
             market_filter=True),
]


# ---------------------------------------------------------------- simulación
@dataclass
class Result:
    trades: list = field(default_factory=list)
    daily: list = field(default_factory=list)


def simulate(strat: Strategy, ind: dict, sessions, cfg: bot.Config) -> Result:
    spy = ind.get("SPY")
    sigs = {s: strat.signals(df, spy) for s, df in ind.items()}
    res = Result()
    pnl_total = 0.0
    for o, c in sessions:
        capital = min(cfg.budget, cfg.budget + pnl_total)
        if capital <= cfg.budget * (1 - cfg.kill_switch_pct / 100):
            res.daily.append((o, 0.0))
            continue
        times = pd.date_range(o, c - timedelta(minutes=5), freq="5min")
        pos: dict[str, dict] = {}
        pending: list = []
        day_pnl, n_trades, stopped = 0.0, 0, False

        def close(sym, price, t, why):
            nonlocal day_pnl
            p = pos.pop(sym)
            px = price * (1 - SLIPPAGE)
            fee = bot.commission(cfg, p["qty"], px)
            pnl = (px - p["entry"]) * p["qty"] - fee - p["fee_in"]
            day_pnl += (px - p["entry"]) * p["qty"] - fee
            res.trades.append({"sym": sym, "day": o, "pnl": pnl, "why": why,
                               "notional": p["entry"] * p["qty"], "fees": fee + p["fee_in"]})

        for t in times:
            flatten = t >= c - timedelta(minutes=cfg.flatten_before_close_min)
            # 1) cierre de fin de sesión o por pérdida diaria
            if flatten or stopped:
                for s in list(pos):
                    row = ind[s]["open"].get(t)
                    if row is not None and not np.isnan(row):
                        close(s, row, t, "cierre")
                if flatten:
                    break
            # 2) ejecutar entradas pendientes a la apertura
            for s, dist in pending:
                if not dist > 0 or s in pos or len(pos) >= cfg.max_positions:
                    continue
                op = ind[s]["open"].get(t)
                if op is None or np.isnan(op):
                    continue
                entry = op * (1 + SLIPPAGE)
                slot = capital / cfg.max_positions
                max_risk = capital * cfg.risk_per_trade_pct / 100
                qty = int(min(slot / entry, max_risk / dist))
                if qty < 1:
                    continue
                tgt_gain = qty * dist * strat.rr
                fee_in = bot.commission(cfg, qty, entry)
                if 2 * fee_in > tgt_gain * cfg.max_commission_share_pct / 100:
                    continue
                pos[s] = {"qty": qty, "entry": entry, "sl": entry - dist, "tp": entry + strat.rr * dist,
                          "fee_in": fee_in}
                day_pnl -= fee_in
                n_trades += 1
            pending = []
            # 3) stops y objetivos dentro de la vela
            for s in list(pos):
                df = ind[s]
                if t not in df.index:
                    continue
                r = df.loc[t]
                p = pos[s]
                if r["low"] <= p["sl"]:
                    close(s, min(p["sl"], r["open"]), t, "stop")
                elif r["high"] >= p["tp"]:
                    close(s, max(p["tp"], r["open"]), t, "objetivo")
            if day_pnl <= -cfg.budget * cfg.daily_loss_limit_pct / 100:
                stopped = True
            # 4) señales al cierre de la vela -> entrada en la siguiente
            tc = t + timedelta(minutes=5)
            in_window = (tc >= o + timedelta(minutes=cfg.no_entry_first_min)
                         and tc <= c - timedelta(minutes=cfg.no_entry_last_min))
            if in_window and not stopped and n_trades < cfg.max_trades_per_day and len(pos) < cfg.max_positions:
                cands = []
                for s, (sig, dist) in sigs.items():
                    if s in pos or t not in sig.index or not sig.at[t]:
                        continue
                    price = ind[s].at[t, "close"]
                    if price < cfg.min_price or price > capital / cfg.max_positions:
                        continue
                    cands.append((ind[s].at[t, "volume"] * price, s, float(dist.at[t])))
                cands.sort(reverse=True)
                pending = [(s, d) for _, s, d in cands[: cfg.max_positions - len(pos)]]
        pnl_total += day_pnl
        res.daily.append((o, day_pnl))
    return res


def stats(res: Result, cfg: bot.Config, days_slice=None) -> dict:
    daily = res.daily if days_slice is None else res.daily[days_slice]
    day_set = {d for d, _ in daily}
    trades = [t for t in res.trades if t["day"] in day_set]
    pnl = np.array([p for _, p in daily])
    eq = cfg.budget + np.cumsum(pnl)
    dd = (eq - np.maximum.accumulate(np.concatenate([[cfg.budget], eq]))[1:]).min() if len(eq) else 0
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] <= 0]
    return {
        "dias": len(daily), "operaciones": len(trades),
        "resultado_$": round(float(pnl.sum()), 2),
        "resultado_%": round(float(pnl.sum()) / cfg.budget * 100, 2),
        "aciertos_%": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "ganancia_media_$": round(float(np.mean(wins)), 2) if wins else 0,
        "perdida_media_$": round(float(np.mean(losses)), 2) if losses else 0,
        "factor_beneficio": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
        "comisiones_$": round(sum(t["fees"] for t in trades), 2),
        "peor_caida_$": round(float(dd), 2),
        "dias_positivos_%": round(float((pnl > 0).sum()) / max(len(pnl), 1) * 100, 1),
    }


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    cfg = bot.Config()
    broker = bot.Alpaca(cfg)
    sessions, raw = fetch(broker, days)
    ind = {s: indicators(regular_hours(df, sessions), sessions) for s, df in raw.items() if len(df) > 200}
    spy = raw.get("SPY")
    bench = None
    if spy is not None:
        spy_r = regular_hours(spy, sessions)
        first, last = spy_r[spy_r.index >= sessions[0][0]]["open"].iloc[0], spy_r["close"].iloc[-1]
        bench = (last / first - 1) * 100
    split = int(len(sessions) * 2 / 3)
    lines = [f"# Simulación de estrategias ({len(sessions)} sesiones: "
             f"{sessions[0][0].date()} a {sessions[-1][0].date()})", "",
             f"Presupuesto {cfg.budget:.0f} $, máx. {cfg.max_positions} posiciones, "
             f"deslizamiento {SLIPPAGE * 100:.2f} % por lado. {len(ind)} valores.", ""]
    if bench is not None:
        lines.append(f"Referencia: comprar SPY y no tocarlo en el mismo periodo = {bench:+.2f} %\n")
    scenarios = [("Trading 212 con saldo en dólares (0 comisión, solo diferencial)", 0.0, 0.0, 100),
                 ("Interactive Brokers Fixed (0,005 $/acc, mín. 1 $)", 0.005, 1.0, 25)]
    for title, per_share, minimum, share in scenarios:
        cfg.commission_per_share, cfg.commission_min, cfg.max_commission_share_pct = per_share, minimum, share
        lines += [f"## {title}", "",
                  "| Estrategia | Periodo | operaciones | resultado % | aciertos % | factor beneficio | comisiones $ | peor caída $ |",
                  "|---|---|---|---|---|---|---|---|"]
        for st in STRATEGIES:
            r = simulate(st, ind, sessions, cfg)
            for label, sl in (("Todo", None), ("1ª parte (2/3)", slice(0, split)), ("2ª parte (1/3)", slice(split, None))):
                x = stats(r, cfg, sl)
                lines.append(f"| {st.name} | {label} | {x['operaciones']} | {x['resultado_%']} | {x['aciertos_%']} "
                             f"| {x['factor_beneficio']} | {x['comisiones_$']} | {x['peor_caida_$']} |")
            print(title, st.name, stats(r, cfg), flush=True)
        lines.append("")
    lines += ["## Estrategias", *[f"- **{s.name}**: {s.desc}" for s in STRATEGIES]]
    with open("BACKTEST.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
