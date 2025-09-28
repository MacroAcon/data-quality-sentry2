#!/usr/bin/env python
"""
Entry point to run Data Quality Sentry checks end‑to‑end.

This script wraps the lower‑level check runner (`checks/run_checks.py`) and
summary writer (`summaries/write_summary.py`) to produce richly formatted
reports with descriptive filenames. It also injects a minimal summary block
into the results JSON so dashboards can be built without reading the full
payload.

Example usage:

```
python run_all.py --source data/sample.csv --out reports_demo --fix --viz on
```

The resulting directory will contain files like `sample__20250101-1200__fix.html`
and `sample__20250101-1200__fix.json`, plus an `index.html` that links to
the most recent report in that folder.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _safe_stem(path: str | None) -> str:
    """Return a safe filesystem stem based on the dataset filename."""
    if not path:
        return "data"
    stem = Path(path).stem
    # replace unsafe characters
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stem) or "data"


def _timestamp() -> str:
    """Return current timestamp suitable for filenames (YYYYMMDD-HHMM)."""
    return datetime.datetime.now().strftime("%Y%m%d-%H%M")


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Run checks and write the HTML report.")
    parser.add_argument(
        "--rules", type=str, default=str(root / "checks" / "rules.yml"), help="Path to rules YAML"
    )
    parser.add_argument(
        "--out", type=str, default=str(root / "reports"), help="Output directory for artefacts"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Path to source CSV. Defaults to the built‑in sample dataset.",
    )
    parser.add_argument("--delimiter", type=str, default=",", help="CSV delimiter")
    parser.add_argument("--encoding", type=str, default="utf-8", help="CSV file encoding")
    parser.add_argument("--redact", choices=["on", "off"], default="on", help="Redact sample values")
    parser.add_argument("--viz", choices=["on", "off"], default="on", help="Generate viz data")
    parser.add_argument("--fix", action="store_true", help="Apply safe fixes to the data")
    parser.add_argument("--fix-dry-run", action="store_true", help="Report fixes without writing cleaned data")
    parser.add_argument(
        "--max-impact-pct",
        type=float,
        default=2.0,
        help="Abort if row drops exceed this percent",
    )
    parser.add_argument(
        "--max-cell-changes-pct",
        type=float,
        default=5.0,
        help="Abort if cell modifications exceed this percent",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional title for the HTML report header",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Optional label appended to the report title",
    )

    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine dataset stem and mode for filenames
    dataset_stem = _safe_stem(args.source)
    mode = "fix" if args.fix else "plain"
    stamp = _timestamp()

    # Run the check runner
    runner_cmd = [
        sys.executable,
        str(root / "checks" / "run_checks.py"),
        "--rules",
        args.rules,
        "--out",
        str(out_dir),
        "--delimiter",
        args.delimiter,
        "--encoding",
        args.encoding,
        "--redact",
        args.redact,
        "--viz",
        args.viz,
        "--max-impact-pct",
        str(args.max_impact_pct),
        "--max-cell-changes-pct",
        str(args.max_cell_changes_pct),
    ]
    if args.source:
        runner_cmd += ["--source_override", args.source]
    if args.fix:
        runner_cmd.append("--fix")
    if args.fix_dry_run:
        runner_cmd.append("--fix-dry-run")

    subprocess.run(runner_cmd, check=True)

    # Insert minimal summary into results.json and copy to descriptive filename
    canonical_results = out_dir / "results.json"
    descriptive_results = out_dir / f"{dataset_stem}__{stamp}__{mode}.json"
    if canonical_results.exists():
        try:
            data = json.loads(canonical_results.read_text(encoding="utf-8"))
            if "summary" not in data:
                checks = data.get("checks", [])
                passed = sum(1 for c in checks if c.get("status") == "pass")
                failed = sum(1 for c in checks if c.get("status") == "fail")
                top_failing = sorted(
                    [c for c in checks if c.get("status") == "fail"],
                    key=lambda c: c.get("count", 0),
                    reverse=True,
                )[:5]
                data["summary"] = {
                    "dataset": args.source or str(Path(root) / "data" / "sample.csv"),
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

    # Build HTML report with descriptive name
    descriptive_html = out_dir / f"{dataset_stem}__{stamp}__{mode}.html"
    writer_cmd = [
        sys.executable,
        str(root / "summaries" / "write_summary.py"),
        "--results",
        str(descriptive_results if descriptive_results.exists() else canonical_results),
        "--out",
        str(descriptive_html),
        "--viz",
        args.viz,
    ]
    if args.title:
        writer_cmd += ["--title", args.title]
    if args.label:
        writer_cmd += ["--label", args.label]
    subprocess.run(writer_cmd, check=True)

    # Write or update a small index.html linking to the latest report
    index_path = out_dir / "index.html"
    index_path.write_text(
        f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>Reports</title>
<style>body{{font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;padding:24px}}a{{display:block;margin:8px 0}}</style>
</head><body><h1>Reports</h1>
<p>Newest report:</p>
<p><a href=\"{descriptive_html.name}\">{descriptive_html.name}</a></p>
</body></html>""",
        encoding="utf-8",
    )

    print(f"Done. Open {descriptive_html}")


if __name__ == "__main__":
    main()