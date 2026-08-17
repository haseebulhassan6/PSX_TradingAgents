from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from .scanner import omniroute_review, scan_kmi30


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="PSX KMI30 Daily Breakout Scanner")
    parser.add_argument("--limit", type=int, default=5, help="Maximum confirmed setups to show")
    parser.add_argument("--no-ai", action="store_true", help="Skip OmniRoute final review")
    parser.add_argument("--show-all", action="store_true", help="Also print all scanned KMI30 results")
    args = parser.parse_args()

    confirmed, all_results = scan_kmi30(limit=max(1, min(args.limit, 5)))

    if not confirmed:
        print("NO CONFIRMED KMI30 BREAKOUT TODAY — WAIT.")
    else:
        print("Rank\tStock\tBreakout Level\tEntry Level\tStop-Loss\tTarget\tRisk/Reward\tSignal")
        for rank, x in enumerate(confirmed, 1):
            print(
                f"{rank}\t{x['stock']}\t{x['breakout_level']:.2f}\t{x['entry']:.2f}\t"
                f"{x['stop_loss']:.2f}\t{x['target']:.2f}\t1:{x['risk_reward']:.2f}\tBUY"
            )

        best = confirmed[0]
        print("\nBest Stock:", best["stock"])
        print("Breakout:", best["breakout_level"])
        print("Entry:", best["entry"])
        print("Stop-Loss:", best["stop_loss"])
        print("Target:", best["target"])
        print("Risk/Reward:", f"1:{best['risk_reward']:.2f}")
        print("Signal: BUY NOW")

    if not args.no_ai:
        try:
            review = omniroute_review(confirmed)
            if review:
                print("\nOmniRoute Risk Review:")
                print(review)
        except Exception as exc:
            print(f"\nOmniRoute review failed: {exc}")

    if args.show_all:
        print("\nAll KMI30 scan results:")
        print(json.dumps(all_results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
