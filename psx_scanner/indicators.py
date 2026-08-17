from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()
    d["rsi14"] = rsi(d["close"], 14)
    d["vol20"] = d["volume"].rolling(20).mean()
    d["volume_ratio"] = d["volume"] / d["vol20"]
    return d


def _recent_pivots(d: pd.DataFrame, lookback: int = 60) -> tuple[float, float]:
    w = d.tail(lookback)
    prev = w.iloc[:-1] if len(w) > 1 else w
    resistance = float(prev["high"].max())
    support = float(prev["low"].min())
    return support, resistance


def evaluate(symbol: str, df: pd.DataFrame) -> dict:
    if len(df) < 55:
        raise ValueError("Need at least 55 daily candles")

    d = enrich(df)
    x = d.iloc[-1]
    support, resistance = _recent_pivots(d, 60)

    close = float(x["close"])
    open_ = float(x["open"])
    high = float(x["high"])
    low = float(x["low"])
    ema20 = float(x["ema20"])
    ema50 = float(x["ema50"])
    rv = float(x["rsi14"]) if not pd.isna(x["rsi14"]) else 0.0
    vr = float(x["volume_ratio"]) if not pd.isna(x["volume_ratio"]) else 0.0

    breakout = close > resistance
    candle_range = max(high - low, 1e-9)
    body = abs(close - open_)
    upper_wick = high - max(close, open_)
    strong_candle = (
        close > open_
        and body / candle_range >= 0.50
        and upper_wick / candle_range <= 0.30
    )
    extended = (close - ema20) / ema20 > 0.10 if ema20 else True

    span = max(resistance - support, 0.0)
    fib38 = resistance - 0.382 * span
    fib50 = resistance - 0.500 * span
    fib62 = resistance - 0.618 * span
    fib127 = support + 1.272 * span
    fib162 = support + 1.618 * span

    recent_low = float(d.iloc[-6:-1]["low"].min())
    stop = min(resistance * 0.998, recent_low)
    risk = close - stop
    measured = resistance + max(resistance - recent_low, 0)
    target_candidates = [v for v in (fib127, fib162, measured) if v > close]
    target = min(target_candidates) if target_candidates else close
    reward = target - close
    rr = reward / risk if risk > 0 else 0.0

    score = 0
    score += 25 if breakout else 0
    score += 20 if vr >= 1.5 else (10 if vr >= 1.2 else 0)
    score += 10 if close > ema20 else 0
    score += 10 if close > ema50 else 0
    score += 10 if 55 <= rv <= 75 else (5 if 50 <= rv < 80 else 0)
    score += 10 if strong_candle else 0
    score += 10 if rr >= 2 else 0
    score += 5 if not extended else 0

    valid = all(
        [
            breakout,
            vr >= 1.2,
            close > ema20,
            close > ema50,
            50 <= rv <= 80,
            strong_candle,
            not extended,
            rr >= 2,
        ]
    )

    if valid:
        signal = "BUY"
    elif breakout and extended:
        signal = "WAIT FOR RETEST"
    else:
        signal = "WAIT FOR BREAKOUT"

    return {
        "stock": symbol,
        "date": str(pd.Timestamp(x["date"]).date()),
        "close": round(close, 2),
        "breakout_level": round(resistance, 2),
        "entry": round(close, 2) if valid else None,
        "stop_loss": round(stop, 2) if valid else None,
        "target": round(target, 2) if valid else None,
        "risk_reward": round(rr, 2),
        "signal": signal,
        "confirmed": valid,
        "score": score,
        "volume_ratio": round(vr, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "rsi": round(rv, 1),
        "strong_candle": strong_candle,
        "extended": extended,
        "fib_38_2": round(fib38, 2),
        "fib_50": round(fib50, 2),
        "fib_61_8": round(fib62, 2),
    }
