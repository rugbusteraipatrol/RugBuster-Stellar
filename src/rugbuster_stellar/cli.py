"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import HorizonClient
from .scanner import StellarAssetScanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan a Stellar Classic asset and issuer using public Horizon evidence."
    )
    parser.add_argument("asset_code", help="Classic asset code, for example USDC")
    parser.add_argument("issuer", help="Classic asset issuer G-address")
    parser.add_argument(
        "--horizon-url",
        default="https://horizon.stellar.org",
        help="Horizon base URL (defaults to Stellar mainnet)",
    )
    parser.add_argument(
        "--max-holders",
        type=int,
        default=200,
        help="Maximum trustline accounts to inspect (1-2000)",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    scanner = StellarAssetScanner(
        HorizonClient(args.horizon_url), max_holders=args.max_holders
    )
    report = scanner.scan(args.asset_code, args.issuer)
    rendered = json.dumps(report, indent=2, sort_keys=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["verdict"] not in {"INSUFFICIENT_DATA", "PARTIAL_ASSESSMENT"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

