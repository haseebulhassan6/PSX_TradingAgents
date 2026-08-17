from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
import re

import pandas as pd
import requests

BASE_URL = "https://dps.psx.com.pk"
HEADERS = {"User-Agent": "Mozilla/5.0 PSX-TradingAgents/1.0"}


def _get(url: str, timeout: int = 20) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def get_kmi30_symbols() -> list[str]:
    """Read the current KMI30 constituent table directly from PSX DPS."""
    html = _get(f"{BASE_URL}/indices/KMI30").text
    try:
        tables = pd.read_html(StringIO(html))
        for table in tables:
            cols = {str(c).strip().upper(): c for c in table.columns}
            if "SYMBOL" in cols:
                vals = table[cols["SYMBOL"]].astype(str).str.strip().tolist()
                vals = [v for v in vals if re.fullmatch(r"[A-Z0-9.-]{1,16}", v)]
                if len(vals) >= 20:
                    return list(dict.fromkeys(vals))[:30]
    except ValueError:
        pass

    candidates = re.findall(r'href=["\']/company/([A-Z0-9.-]+)["\']', html)
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) >= 20:
        return candidates[:30]
    raise RuntimeError("Could not read KMI30 constituents from PSX DPS.")


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if isinstance(d.index, pd.DatetimeIndex) and "date" not in [str(c).lower() for c in d.columns]:
        d = d.reset_index()
    d.columns = [str(c).strip().lower().replace(" ", "_") for c in d.columns]
    aliases = {
        "date": ("date", "datetime", "timestamp", "index"),
        "open": ("open", "open_price"),
        "high": ("high", "high_price"),
        "low": ("low", "low_price"),
        "close": ("close", "price", "current"),
        "volume": ("volume", "vol"),
    }
    out: dict[str, pd.Series] = {}
    for target, names in aliases.items():
        source = next((n for n in names if n in d.columns), None)
        if source is not None:
            out[target] = d[source]
    result = pd.DataFrame(out)
    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(result.columns):
        missing = sorted(required - set(result.columns))
        raise RuntimeError(f"OHLCV data missing columns: {', '.join(missing)}")
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        result[c] = pd.to_numeric(result[c], errors="coerce")
    return (
        result.dropna(subset=["date", "open", "high", "low", "close", "volume"])
        .sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )


def get_eod(symbol: str, lookback_days: int = 420) -> pd.DataFrame:
    """Fetch daily OHLCV.

    Preferred source is the open-source ``psxdata`` package, which reads public PSX
    pages and provides full OHLCV. A direct DPS timeseries fallback is retained for
    diagnostics, but it is rejected when high/low are unavailable because this
    scanner will not manufacture candlestick or support/resistance data.
    """
    try:
        import psxdata  # type: ignore

        end = date.today()
        start = end - timedelta(days=lookback_days)
        df = psxdata.stocks(symbol, start=start.isoformat(), end=end.isoformat())
        normalized = _normalize_ohlcv(df)
        if len(normalized) >= 55:
            return normalized
    except Exception:
        pass

    payload = _get(f"{BASE_URL}/timeseries/eod/{symbol}").json()
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"No EOD data returned for {symbol}")

    first = rows[0]
    if not isinstance(first, (list, tuple)):
        raise RuntimeError(f"Unsupported PSX EOD response for {symbol}")

    # DPS /timeseries/eod commonly returns timestamp, close, volume, open only.
    # That is insufficient for high-precision candlestick/support analysis.
    if len(first) < 6:
        raise RuntimeError(
            "Direct PSX EOD feed does not include full OHLCV. Install psxdata and retry."
        )

    width = len(first)
    df = pd.DataFrame(
        rows,
        columns=["date", "open", "high", "low", "close", "volume", *[f"x{i}" for i in range(width - 6)]],
    )
    return _normalize_ohlcv(df[["date", "open", "high", "low", "close", "volume"]])
