#!/usr/bin/env python
from __future__ import annotations
import sys, subprocess, hashlib, shutil
from pathlib import Path
import argparse, datetime, json

def _safe_stem(p: str | None) -> str:
    if not p: return "sample"
    stem = Path(p).stem
    return "".join(c if c.isalnum() or c in ("-","_") else "_" for c in stem) or "sample"

def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M")

def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Run checks and write the HTML report.")
    parser.add_argument("--rules", type=str, default=str(root / "checks" / "rules.yml"))
    parser.add_argument("--out", type=str, default=str(root / "reports"))
    parser.add_argument("--source", type=str, default=None, help="Optional CSV (e.g., data/file.csv)")
    parser.add_argument("--delimiter", type=str, default=",")
    parser.add_argument("--encoding", type=str, default="utf-8")
    parser.add_argument("--redact", choices=["on","off"], default="on")
    parser.add_argument("--viz", choices=["on","off"], default="on")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--fix-dry-run", action="store_true")
    parser.add_argument("--max-impact-pct", type=float, default=2.0)
    parser.add_argument("--max-cell-changes-pct", type=float, default=5.0)
    parser.add_argument("--title", type=str, default=None, help="Optional title for the HTML report")
    parser.add_argument("--label", type=str, default=None, help="Optional label (e.g., staging, run-42)")
    args = parser.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    # Build descriptive names
    dataset_stem = _safe_stem(args.source)
    mode = "fix" if args.fix else "plain"
    stamp = _timestamp()

    # Run checks
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

    # Move canonical results.json to descriptive filename
    canonical_results = out_dir/"results.json"
    descriptive_results = out_dir / f"{dataset_stem}__{stamp}__{mode}.json"
    if canonical_results.exists():
        # augment with summary + metadata if missing
        try:
            data = json.loads(canonical_results.read_text(encoding="utf-8"))
            if "summary" not in data:
                # minimal summary build
                checks = data.get("checks", [])
                passed = sum(1 for c in checks if c.get("status") == "pass")
                failed = sum(1 for c in checks if c.get("status") == "fail")
                top_failing = sorted(
                    [c for c in checks if c.get("status")=="fail"],
                    key=lambda c: c.get("count", 0),
                    reverse=True
                )[:5]
                data["summary"] = {
                    "dataset": args.source or "data/sample.csv",
                    "mode": mode,
                    "timestamp": stamp,
                    "passed": passed,
                    "failed": failed,
                    "top_failing": top_failing,
                }
                canonical_results.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass
        shutil.copy2(canonical_results, descriptive_results)

    # Build HTML with descriptive name
    html_path = out_dir / f"{dataset_stem}__{stamp}__{mode}.html"
    cmd2 = [sys.executable, str(root/"summaries"/"write_summary.py"),
            "--results", str(descriptive_results if descriptive_results.exists() else canonical_results),
            "--out", str(html_path),
            "--viz", args.viz]
    if args.title:
        cmd2 += ["--title", args.title]
    if args.label:
        cmd2 += ["--label", args.label]
    subprocess.run(cmd2, check=True)

    # Write or update a tiny index.html that links to the newest report
    index_html = out_dir / "index.html"
    index_html.write_text(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Reports</title>
<style>body{{font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;padding:24px}}
a{{display:block;margin:8px 0}}</style></head>
<body><h1>Reports</h1>
<p>Newest report written:</p>
<p><a href="{html_path.name}">{html_path.name}</a></p>
</body></html>""", encoding="utf-8")

    print(f"Done. Open {html_path}")

if __name__ == "__main__":
    main()
