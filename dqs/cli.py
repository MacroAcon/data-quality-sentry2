from __future__ import annotations
import sys, subprocess
from pathlib import Path
import argparse

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Data Quality Sentry CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Run checks and write HTML report")
    p_run.add_argument("--rules", type=str, default=str(root / "checks" / "rules.yml"))
    p_run.add_argument("--out", type=str, default=str(root / "reports"))
    p_run.add_argument("--source", type=str, default=None)
    p_run.add_argument("--delimiter", type=str, default=",")
    p_run.add_argument("--encoding", type=str, default="utf-8")
    p_run.add_argument("--redact", choices=["on","off"], default="on")
    p_run.add_argument("--viz", choices=["on","off"], default="on")
    p_run.add_argument("--fix", action="store_true")
    p_run.add_argument("--fix-dry-run", action="store_true")
    p_run.add_argument("--max-impact-pct", type=float, default=2.0)
    p_run.add_argument("--max-cell-changes-pct", type=float, default=5.0)

    args = parser.parse_args()
    if args.cmd is None:
        args = parser.parse_args(["run"])

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

    cmd2 = [sys.executable, str(root/"summaries"/"write_summary.py"),
            "--results", str(out_dir/"results.json"), "--out", str(out_dir/"index.html"), "--viz", args.viz]
    subprocess.run(cmd2, check=True)
    print(f"Done. Open {out_dir/'index.html'}")
