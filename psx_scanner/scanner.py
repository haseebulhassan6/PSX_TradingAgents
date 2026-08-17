from __future__ import annotations

import json
import os
from typing import Iterable

import requests

from .data import get_eod, get_kmi30_symbols
from .indicators import evaluate


def scan_kmi30(limit: int = 5) -> tuple[list[dict], list[dict]]:
    """Scan all current KMI30 constituents.

    Returns (confirmed_setups, all_results). Weak stocks are never promoted to BUY.
    """
    results: list[dict] = []
    for symbol in get_kmi30_symbols():
        try:
            result = evaluate(symbol, get_eod(symbol))
            results.append(result)
        except Exception as exc:  # one bad ticker must not abort the complete index scan
            results.append({"stock": symbol, "confirmed": False, "signal": "DATA ERROR", "error": str(exc), "score": -1})

    ranked = sorted(results, key=lambda x: (bool(x.get("confirmed")), x.get("score", -1)), reverse=True)
    confirmed = [r for r in ranked if r.get("confirmed")][:limit]
    return confirmed, ranked


def omniroute_review(setups: Iterable[dict]) -> str | None:
    """Ask OmniRoute to challenge confirmed setups; it may reject, never invent levels."""
    setups = list(setups)
    if not setups:
        return None

    base_url = os.getenv("TRADINGAGENTS_LLM_BACKEND_URL", "http://localhost:20128/v1").rstrip("/")
    api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
    model = os.getenv("TRADINGAGENTS_DEEP_THINK_LLM", "auto")
    if not api_key:
        return "OmniRoute review skipped: OPENAI_COMPATIBLE_API_KEY is not set."

    system = (
        "You are the final risk reviewer for a Pakistan Stock Exchange KMI30 breakout scanner. "
        "The supplied numeric levels were calculated by deterministic Python code. Do not alter, "
        "invent, recalculate, or add prices. You may only approve or reject each setup. Reject if "
        "the evidence is weak, extended, or inconsistent. Use simple English. Return concise JSON "
        "with keys best_stock, signal, reason and rejected_stocks. signal must be BUY NOW, BUY ON RETEST, WAIT, or NO TRADE."
    )
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(setups, ensure_ascii=False)},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]
