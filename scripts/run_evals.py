#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evals import DEFAULT_CASES_PATH, run_regression_evals


def main() -> int:
    parser = argparse.ArgumentParser(description="Run regression evals for tools and agents.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--name", default="", help="Run only cases whose name contains this substring.")
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    summary = run_regression_evals(
        cases_path=args.cases,
        name_filter=args.name,
        include_optional=args.include_optional,
    )

    if args.output:
        Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for item in summary["results"]:
        status = str(item["status"]).upper()
        line = f"[{status}] {item['name']}"
        if item["status"] == "skipped":
            line += f" - {item.get('reason', '')}"
        elif item["status"] == "failed":
            line += f" - {'; '.join(item.get('errors') or [])}"
        print(line)

    print(
        f"\nSummary: passed={summary['passed']} failed={summary['failed']} "
        f"skipped={summary['skipped']} total={summary['total']}"
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
