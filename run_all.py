#!/usr/bin/env python
from __future__ import annotations
import sys, subprocess
from pathlib import Path
import argparse

def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Run checks and write the HTML report.")
    parser.add_argument("--rules", type=str, default=str(root / "checks" / "rules.yml"))
    parser.add_argument("--out", type=str, default=str(root / "reports"))
    parser.add_argument("--source", type=str, default=None, help="Optional source override (e.g., data/fail_cases.csv)")
    parser.add_argument("--delimiter", type=str, default=",")
    parser.add_argument("--encoding", type=str, default="utf-8")
    parser.add_argument("--redact", choices=["on","off"], default="on")
    parser.add_argument("--viz", choices=["on","off"], default="on")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--fix-dry-run", action="store_true")
    parser.add_argument("--max-impact-pct", type=float, default=2.0)
    parser.add_argument("--max-cell-changes-pct", type=float, default=5.0)
    args = parser.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    cmd1 = [sys.executable, str(root/"checks"/"run_checks.py"),
            "--rules", args.rules, "--out", str(out_dir),
            "--delimiter", args.delimiter, "--encoding", args.encoding, "--redact", args.redact, "--viz", args.viz,
            "--max-impact-pct", str(args.max_impact_pct), "--max-cell-changes-pct", str(args.max_cell_changes_pct)]
    if args.source:
        cmd1 += ["--source_override", args.source]
    if args.fix:
        cmd1 += ["--fix"]
    if args.fix_dry_run:
        cmd1 += ["--fix-dry-run"]
    subprocess.run(cmd1, check=True)

    html_path = out_dir/"index.html"
    cmd2 = [sys.executable, str(root/"summaries"/"write_summary.py"),
            "--results", str(out_dir/"results.json"), "--out", str(html_path), "--viz", args.viz]
    subprocess.run(cmd2, check=True)
    print(f"Done. Open {html_path}")

if __name__ == "__main__":
    main()
