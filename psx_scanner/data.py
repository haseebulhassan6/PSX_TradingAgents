from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import re

import pandas as pd
import requests

BASE_URL = "https://dps.psx.com.pk"
HEADERS = {"User-Agent": "Mozilla/5.0 PSX-TradingAgents/1.0"}


@dataclass
class MarketSnapshot:
    kmi30_change_pct: float | None = None
    kse100_change_pct: float | None = None


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

    # Fallback for minor HTML layout changes.
    candidates = re.findall(r'href=["\']/company/([A-Z0-9.-]+)["\']', html)
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) >= 20:
        return candidates[:30]
    raise RuntimeError("Could not read KMI30 constituents from PSX DPS.")


def get_eod(symbol: str) -> pd.DataFrame:
    """Fetch PSX end-of-day series and normalize to date/open/high/low/close/volume.

    PSX currently exposes /timeseries/eod/{SYMBOL}. The response format has changed
    historically, so this parser accepts common list/dict shapes.
    """
    payload = _get(f"{BASE_URL}/timeseries/eod/{symbol}").json()
    rows = payload
    if isinstance(payload, dict):
        for key in ("data", "timeseries", "series", "rows"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"No EOD data returned for {symbol}")

    first = rows[0]
    if isinstance(first, dict):
        df = pd.DataFrame(rows)
        aliases = {
            "date": ["date", "time", "timestamp", "datetime"],
            "open": ["open", "o"],
            "high": ["high", "h"],
            "low": ["low", "l"],
            "close": ["close", "c", "price"],
            "volume": ["volume", "v", "vol"],
        }
        out = {}
        lower = {str(c).lower(): c for c in df.columns}
        for target, names in aliases.items():
            source = next((lower[n] for n in names if n in lower), None)
            if source is not None:
                out[target] = df[source]
        df = pd.DataFrame(out)
    else:
        # Common PSX compact series are timestamp + OHLCV or timestamp + close + volume.
        width = len(first) if isinstance(first, (list, tuple)) else 0
        if width >= 6:
            df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", *[f"x{i}" for i in range(width - 6)]])
            df = df[["date", "open", "high", "low", "close", "volume"]]
        elif width == 3:
            df = pd.DataFrame(rows, columns=["date", "close", "volume"])
            df["open"] = df["close"]
            df["high"] = df["close"]
            df["low"] = df["close"]
        else:
            raise RuntimeError(f"Unsupported PSX EOD response shape for {symbol}")

    required = {"date", "close", "volume"}
    if not required.issubset(df.columns):
        raise RuntimeError(f"PSX EOD response for {symbol} is missing required fields")

    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Numeric epoch values are normally seconds; pandas also handles normal date strings.
    if pd.api.types.is_numeric_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], unit="s", errors="coerce")
    else:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
    return df.reset_index(drop=True)
