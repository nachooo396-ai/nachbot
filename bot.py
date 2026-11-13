"""
NachBot - bot de trading intradía para Alpaca (por defecto, dinero ficticio).

Cada ejecución hace UNA pasada (pensado para lanzarse cada 10 min con GitHub Actions):
  1. Comprueba que el mercado está abierto.
  2. Calcula el capital con el que puede operar (presupuesto fijo; las ganancias se apartan).
  3. Aplica los frenos de seguridad (pérdida diaria, pérdida total, cierre antes del final del día).
  4. Busca señales en la lista de acciones y abre operaciones con stop-loss y take-profit.

Variables de entorno obligatorias: ALPACA_KEY, ALPACA_SECRET
Opcionales: ver CONFIG más abajo.
"""
from __future__ import annotations

import os
import subprocess
import time
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    return float(v) if v not in (None, "") else default


@dataclass
class Config:
    live: bool = os.getenv("LIVE", "false").lower() == "true"   # False = dinero ficticio
    budget: float = env_float("BUDGET", 1000)                  # capital máximo con el que opera
    start_equity: float = env_float("START_EQUITY", 100000)    # saldo de la cuenta al arrancar el bot
    max_positions: int = int(env_float("MAX_POSITIONS", 3))
    take_profit_pct: float = env_float("TAKE_PROFIT_PCT", 1.5)  # +1.5 %
    stop_loss_pct: float = env_float("STOP_LOSS_PCT", 0.75)     # -0.75 %
    risk_per_trade_pct: float = env_float("RISK_PER_TRADE_PCT", 1.0)  # máx. 1 % del capital en riesgo por operación
    daily_loss_limit_pct: float = env_float("DAILY_LOSS_LIMIT_PCT", 3.0)  # para el día si pierde 3 % del presupuesto
    kill_switch_pct: float = env_float("KILL_SWITCH_PCT", 25.0)  # se apaga del todo si pierde 25 % del presupuesto
    max_trades_per_day: int = int(env_float("MAX_TRADES_PER_DAY", 8))
    no_entry_first_min: int = 15   # no entra en los primeros 15 min (mucho ruido)
    no_entry_last_min: int = 30    # no entra en los últimos 30 min
    flatten_before_close_min: int = 10  # cierra todo 10 min antes del cierre
    top_actives: int = int(env_float("TOP_ACTIVES", 100))  # nº de acciones más negociadas a revisar
    min_price: float = env_float("MIN_PRICE", 5)  # ignora acciones de menos de 5 $ (muy especulativas)
    watchlist: tuple = tuple(os.getenv(
        "WATCHLIST", "SPY,QQQ,AAPL,MSFT,NVDA,AMD,META,AMZN,TSLA,GOOGL").split(","))

    @property
    def base_url(self) -> str:
        return "https://api.alpaca.markets" if self.live else "https://paper-api.alpaca.markets"


DATA_URL = "https://data.alpaca.markets"


# ---------------------------------------------------------------- Broker (Alpaca REST)
class Alpaca:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({
            "APCA-API-KEY-ID": os.environ["ALPACA_KEY"],
            "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET"],
        })

    def _req(self, method, url, **kw):
        r = self.s.request(method, url, timeout=20, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text}")
        return r.json() if r.text else None

    def clock(self):
        return self._req("GET", f"{self.cfg.base_url}/v2/clock")

    def account(self):
        return self._req("GET", f"{self.cfg.base_url}/v2/account")

    def session_open(self, next_close: datetime) -> datetime:
        """Hora real de apertura de hoy (tiene en cuenta días de media sesión)."""
        day = next_close.astimezone(NY).date().isoformat()
        cal = self._req("GET", f"{self.cfg.base_url}/v2/calendar", params={"start": day, "end": day})
        hh, mm = cal[0]["open"].split(":")
        return datetime.fromisoformat(f"{day}T{hh}:{mm}:00").replace(tzinfo=NY)

    def positions(self):
        return self._req("GET", f"{self.cfg.base_url}/v2/positions")

    def open_orders(self):
        return self._req("GET", f"{self.cfg.base_url}/v2/orders", params={"status": "open", "limit": 500})

    def orders_since(self, since: datetime):
        return self._req("GET", f"{self.cfg.base_url}/v2/orders",
                         params={"status": "all", "after": since.isoformat(), "limit": 500})

    def close_all(self):
        self._req("DELETE", f"{self.cfg.base_url}/v2/orders")
        self._req("DELETE", f"{self.cfg.base_url}/v2/positions", params={"cancel_orders": "true"})

    def bars(self, symbol: str, start: datetime) -> pd.DataFrame:
        data = self._req("GET", f"{DATA_URL}/v2/stocks/{symbol}/bars", params={
            "timeframe": "5Min", "start": start.isoformat(), "feed": "iex",
            "adjustment": "raw", "limit": 1000})
        rows = data.get("bars") or []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).rename(columns={"t": "time", "o": "open", "h": "high",
                                                "l": "low", "c": "close", "v": "volume"})
        df["time"] = pd.to_datetime(df["time"])
        return df

    def most_actives(self, top: int) -> list[str]:
        data = self._req("GET", f"{DATA_URL}/v1beta1/screener/stocks/most-actives",
                         params={"by": "volume", "top": top})
        return [m["symbol"] for m in data.get("most_actives", [])]

    def bars_multi(self, symbols: list[str], start: datetime) -> dict:
        """Velas de 5 min de muchos valores a la vez (por bloques de 50)."""
        out: dict[str, list] = {}
        for i in range(0, len(symbols), 50):
            chunk = symbols[i:i + 50]
            token = None
            while True:
                params = {"symbols": ",".join(chunk), "timeframe": "5Min", "start": start.isoformat(),
                          "feed": "iex", "adjustment": "raw", "limit": 10000}
                if token:
                    params["page_token"] = token
                data = self._req("GET", f"{DATA_URL}/v2/stocks/bars", params=params)
                for sym, rows in (data.get("bars") or {}).items():
                    out.setdefault(sym, []).extend(rows)
                token = data.get("next_page_token")
                if not token:
                    break
        result = {}
        for sym, rows in out.items():
            df = pd.DataFrame(rows).rename(columns={"t": "time", "o": "open", "h": "high",
                                                    "l": "low", "c": "close", "v": "volume"})
            df["time"] = pd.to_datetime(df["time"])
            result[sym] = df.sort_values("time").reset_index(drop=True)
        return result

    def buy_bracket(self, symbol: str, qty: int, take_profit: float, stop_loss: float):
        return self._req("POST", f"{self.cfg.base_url}/v2/orders", json={
            "symbol": symbol, "qty": str(qty), "side": "buy", "type": "market",
            "time_in_force": "gtc", "order_class": "bracket",
            "take_profit": {"limit_price": f"{take_profit:.2f}"},
            "stop_loss": {"stop_price": f"{stop_loss:.2f}"},
        })


# ---------------------------------------------------------------- Lógica (funciones puras, testeables)
def trading_capital(cfg: Config, equity: float) -> tuple[float, float]:
    """Devuelve (capital_para_operar, ganancias_retirables).
    Si va ganando, opera solo con el presupuesto y aparta lo ganado.
    Si va perdiendo, opera con lo que queda (nunca mete más)."""
    pnl_total = equity - cfg.start_equity
    if pnl_total >= 0:
        return cfg.budget, pnl_total
    return max(cfg.budget + pnl_total, 0.0), 0.0


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / down.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def entry_signal(df: pd.DataFrame, session_open: datetime) -> bool:
    """Señal de compra con la última vela cerrada de 5 min (usa también velas de días anteriores,
    así puede dar señales desde el principio de la sesión):
    - la media rápida (EMA 9) acaba de cruzar por encima de la lenta (EMA 21): impulso al alza
    - el precio está por encima del VWAP de hoy: compradores dominando el día
    - RSI entre 50 y 70: fuerza, pero sin estar ya sobrecomprado."""
    if len(df) < 30:
        return False
    today = df[df["time"] >= session_open]
    if today.empty or df["time"].iloc[-1] < session_open:
        return False
    c = df["close"]
    e9, e21 = ema(c, 9), ema(c, 21)
    tp = (today["high"] + today["low"] + today["close"]) / 3
    vwap = (tp * today["volume"]).sum() / max(today["volume"].sum(), 1e-9)
    r = rsi(c)
    crossed = e9.iloc[-2] <= e21.iloc[-2] and e9.iloc[-1] > e21.iloc[-1]
    return bool(crossed and c.iloc[-1] > vwap and 50 <= r.iloc[-1] <= 70)


def position_size(cfg: Config, capital: float, price: float) -> int:
    """Nº de acciones: reparte el capital entre los huecos y limita lo que se puede perder."""
    per_slot = capital / cfg.max_positions
    max_risk = capital * cfg.risk_per_trade_pct / 100
    by_risk = max_risk / (price * cfg.stop_loss_pct / 100)
    return int(min(per_slot / price, by_risk))


# ---------------------------------------------------------------- Una pasada del bot
def run(broker, cfg: Config, now: datetime | None = None) -> list[str]:
    log: list[str] = []
    now = now or datetime.now(timezone.utc)
    mode = "REAL" if cfg.live else "PRÁCTICA (dinero ficticio)"
    log.append(f"Modo: {mode}")

    clock = broker.clock()
    if not clock["is_open"]:
        log.append("Mercado cerrado. Nada que hacer.")
        return log

    acct = broker.account()
    equity, last_equity = float(acct["equity"]), float(acct["last_equity"])
    capital, retirable = trading_capital(cfg, equity)
    day_pnl = equity - last_equity
    log.append(f"Capital para operar: {capital:.2f} $ | Ganancias apartadas para retirar: {retirable:.2f} $ "
               f"| Resultado de hoy: {day_pnl:+.2f} $")

    # Freno 1: se ha perdido demasiado en total -> apagado
    if capital <= cfg.budget * (1 - cfg.kill_switch_pct / 100):
        broker.close_all()
        log.append(f"APAGADO: pérdida total ≥ {cfg.kill_switch_pct}% del presupuesto. Cierro todo y no opero más.")
        return log

    # Freno 2: mal día -> cierra y para hasta mañana
    if day_pnl <= -cfg.budget * cfg.daily_loss_limit_pct / 100:
        broker.close_all()
        log.append(f"STOP DEL DÍA: pérdida de hoy ≥ {cfg.daily_loss_limit_pct}% del presupuesto. Cierro todo.")
        return log

    # Freno 3: cerca del cierre -> nada abierto de un día para otro
    next_close = datetime.fromisoformat(clock["next_close"])
    mins_to_close = (next_close - now).total_seconds() / 60
    if mins_to_close <= cfg.flatten_before_close_min:
        broker.close_all()
        log.append("Fin de sesión: cierro todas las posiciones.")
        return log

    session_open = broker.session_open(next_close)
    mins_since_open = (now - session_open).total_seconds() / 60
    if mins_since_open < cfg.no_entry_first_min or mins_to_close < cfg.no_entry_last_min:
        log.append("Fuera de la ventana de entradas (inicio o final de sesión).")
        return log

    positions = broker.positions()
    held = {p["symbol"] for p in positions}
    pending = {o["symbol"] for o in broker.open_orders() if o["side"] == "buy"}
    entries_today = [o for o in broker.orders_since(session_open)
                     if o["side"] == "buy" and o.get("order_class") == "bracket"]
    slots = cfg.max_positions - len(held)
    if len(entries_today) >= cfg.max_trades_per_day:
        log.append(f"Límite de {cfg.max_trades_per_day} operaciones hoy alcanzado.")
        return log
    if slots <= 0:
        log.append(f"Ya hay {len(held)} posiciones abiertas (máximo {cfg.max_positions}).")
        return log

    # Universo: las más negociadas del momento + la lista fija
    try:
        actives = broker.most_actives(cfg.top_actives)
    except Exception:  # noqa: BLE001
        actives = []
    universe = []
    for sym in list(actives) + [w.strip().upper() for w in cfg.watchlist]:
        if sym and sym not in universe and sym not in held and sym not in pending:
            universe.append(sym)

    # Solo velas ya cerradas; se piden también los días anteriores para tener historial
    last_closed = now - timedelta(minutes=5)
    all_bars = broker.bars_multi(universe, session_open - timedelta(days=4))
    max_price = capital / cfg.max_positions
    with_data, up, near, too_expensive = 0, 0, [], 0
    for sym in universe:
        if slots <= 0:
            break
        df = all_bars.get(sym)
        if df is None or df.empty:
            continue
        df = df[df["time"] <= last_closed]
        if len(df) < 30 or df["time"].iloc[-1] < session_open:
            continue
        with_data += 1
        price = float(df["close"].iloc[-1])
        e9, e21 = ema(df["close"], 9).iloc[-1], ema(df["close"], 21).iloc[-1]
        if e9 > e21:
            up += 1
        elif (e21 - e9) / e21 < 0.0005:
            near.append(sym)
        if price < cfg.min_price:
            continue
        if price > max_price:
            too_expensive += 1
            continue
        if not entry_signal(df, session_open):
            continue
        qty = position_size(cfg, capital, price)
        if qty < 1:
            continue
        tp = price * (1 + cfg.take_profit_pct / 100)
        sl = price * (1 - cfg.stop_loss_pct / 100)
        broker.buy_bracket(sym, qty, tp, sl)
        slots -= 1
        log.append(f"COMPRA {sym}: {qty} acc. a ~{price:.2f} $ | objetivo {tp:.2f} | stop {sl:.2f}")

    log.append(f"Valores revisados: {with_data} (de {len(universe)}) | en tendencia alcista: {up}"
               + (f" | demasiado caros para el capital: {too_expensive}" if too_expensive else "")
               + (f" | a punto de dar señal: {', '.join(near[:8])}" if near else ""))
    if not any(l.startswith("COMPRA") for l in log):
        log.append("Sin señales de entrada en esta pasada.")
    return log


def save_status(lines: list[str]):
    """Guarda el resultado en la rama 'estado' (si existe el script; en local no hace nada)."""
    print("\n".join(lines), flush=True)
    with open("salida.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    if os.path.exists("guardar_estado.sh") and os.getenv("GITHUB_ACTIONS"):
        subprocess.run(["bash", "guardar_estado.sh"], check=False)


def dispatch_next_run():
    """Lanza una nueva ejecución del workflow (para seguir vigilando más allá del límite de 6 h)."""
    repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (repo and token):
        return
    requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/bot.yml/dispatches",
                  headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                  json={"ref": "main"}, timeout=20)


def loop(cfg: Config, every_min: int = 5, max_hours: float = 5.6, wait_open_hours: float = 2):
    """Vigila sin parar mientras la bolsa está abierta: una pasada cada `every_min` minutos.
    Si la bolsa abre en menos de `wait_open_hours`, espera a que abra. Termina al cerrar."""
    broker = Alpaca(cfg)
    started = time.time()
    while True:
        try:
            clock = broker.clock()
            now = datetime.now(timezone.utc)
            if not clock["is_open"]:
                wait = (datetime.fromisoformat(clock["next_open"]) - now).total_seconds()
                if 0 < wait <= wait_open_hours * 3600 and time.time() - started + wait < max_hours * 3600:
                    print(f"Bolsa cerrada; espero {wait / 60:.0f} min a que abra.", flush=True)
                    time.sleep(wait + 60)
                    continue
                save_status([f"Modo: {'REAL' if cfg.live else 'PRÁCTICA (dinero ficticio)'}",
                             "Bolsa cerrada. Fin de la vigilancia de hoy."])
                return
            save_status(run(broker, cfg, now))
        except Exception as e:  # noqa: BLE001
            save_status([f"ERROR: {e}"])
        if time.time() - started > max_hours * 3600:
            print("Límite de tiempo de GitHub cerca: lanzo una nueva ejecución para seguir.", flush=True)
            dispatch_next_run()
            return
        time.sleep(every_min * 60)


def main():
    cfg = Config()
    if "--loop" in sys.argv:
        loop(cfg)
        return
    try:
        lines = run(Alpaca(cfg), cfg)
    except Exception as e:  # noqa: BLE001
        lines = [f"ERROR: {e}"]
        save_status(lines)
        sys.exit(1)
    save_status(lines)


if __name__ == "__main__":
    main()
