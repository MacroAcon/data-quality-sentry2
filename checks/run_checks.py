from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import yaml
try:
    from .fixers import (FixReport, trim_strings, drop_exact_duplicates, clip_range, enforce_enum, fill_nulls, parse_dates)
except Exception:
    from fixers import (FixReport, trim_strings, drop_exact_duplicates, clip_range, enforce_enum, fill_nulls, parse_dates)

def main():
    p = argparse.ArgumentParser(description="Run data quality checks (turnkey).")
    p.add_argument("--rules", type=str, required=True)
    p.add_argument("--out", type=str, required=True)
    p.add_argument("--source_override", type=str, default=None)
    p.add_argument("--delimiter", type=str, default=",")
    p.add_argument("--encoding", type=str, default="utf-8")
    p.add_argument("--redact", choices=["on","off"], default="on")
    p.add_argument("--viz", choices=["on","off"], default="on", help="Enable viz data")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--fix-dry-run", action="store_true")
    p.add_argument("--max-impact-pct", type=float, default=2.0, help="Abort if row drops exceed this percent")
    p.add_argument("--max-cell-changes-pct", type=float, default=5.0, help="Abort if cell modifications exceed this percent")
    args = p.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    rules = yaml.safe_load(Path(args.rules).read_text(encoding="utf-8"))
    default_src = Path(__file__).resolve().parents[1]/"data"/"sample.csv"
    src = args.source_override or str(default_src)
    df = pd.read_csv(src, delimiter=args.delimiter, encoding=args.encoding)

    # helpers
    def _mask_range(series, min_v, max_v):
        s = pd.to_numeric(series, errors="coerce")
        m = ((s < min_v) if min_v is not None else False) | ((s > max_v) if max_v is not None else False)
        return m.fillna(False)
    def _mask_enum(series, allowed):
        return (~series.isin(allowed)).fillna(True)
    def _mask_duplicate(df, subset):
        return df.duplicated(subset=subset or df.columns.tolist(), keep="first")
    def _mask_freshness(series, max_age_days=None, parse_format=None):
        parsed = pd.to_datetime(series, format=parse_format, errors="coerce")
        if max_age_days is None:
            return (parsed.isna() & series.notna())
        age = (pd.Timestamp.utcnow().tz_localize(None) - parsed).dt.days
        return (parsed.isna() & series.notna()) | (age > max_age_days)

    # Evaluate
    checks = []; passed=0; failed=0
    for t in rules.get("tables", []):
        tname = t.get("name","table")

        for chk in t.get("checks", []):
            if chk.get("type") == "duplicate":
                subset = chk.get("subset")
                mask = _mask_duplicate(df, subset)
                cnt = int(mask.sum()); status = "fail" if cnt>0 else "pass"
                checks.append({"name": f"{tname}.duplicate", "table": tname, "column": None, "type": "duplicate",
                               "status": status, "count": cnt, "params": {"subset": subset}})
                failed += (status=="fail"); passed += (status=="pass")

        for col in t.get("columns", []):
            cname = col.get("name"); 
            if cname not in df.columns: 
                continue
            for chk in col.get("checks", []):
                ctype = chk.get("type"); params = {}; status="pass"; count=0
                if ctype == "range":
                    min_v, max_v = chk.get("min"), chk.get("max"); params={"min":min_v,"max":max_v}
                    mask = _mask_range(df[cname], min_v, max_v); count=int(mask.sum()); status="fail" if count>0 else "pass"
                elif ctype == "enum":
                    allowed = chk.get("allowed", []); params={"allowed":allowed}
                    mask = _mask_enum(df[cname], allowed); count=int(mask.sum()); status="fail" if count>0 else "pass"
                elif ctype == "null_rate":
                    max_nulls = chk.get("max_nulls"); max_null_frac = chk.get("max_null_frac")
                    params={"max_nulls": max_nulls, "max_null_frac": max_null_frac}
                    nulls = df[cname].isna(); count=int(nulls.sum())
                    ok_by_count = (max_nulls is None) or (count <= max_nulls)
                    frac = count / max(1, len(df))
                    ok_by_frac = (max_null_frac is None) or (frac <= max_null_frac)
                    mask = nulls; status = "pass" if (ok_by_count and ok_by_frac) else "fail"
                elif ctype == "freshness":
                    max_age_days = chk.get("max_age_days"); parse_format = chk.get("parse_format")
                    params={"max_age_days": max_age_days, "parse_format": parse_format}
                    mask = _mask_freshness(df[cname], max_age_days, parse_format); count=int(mask.sum())
                    status = "fail" if max_age_days is not None and count>0 else "pass"
                else:
                    mask = pd.Series(False, index=df.index)

                checks.append({"name": f"{tname}.{cname}.{ctype}", "table": tname, "column": cname, "type": ctype,
                               "status": status, "count": count, "params": params})
                failed += (status=="fail"); passed += (status=="pass")

    # Per-rule failure samples
    samples_dir = out_dir / "failures"; samples_dir.mkdir(parents=True, exist_ok=True)
    failure_samples = {}
    for c in checks:
        if c["status"] != "fail": continue
        ctype = c["type"]; cname = c.get("column"); fname = c["name"].replace(".","_") + ".csv"; fpath = samples_dir / fname
        mask = None
        if ctype == "duplicate":
            subset = c["params"].get("subset"); mask = _mask_duplicate(df, subset)
        elif ctype == "range" and cname in df.columns:
            p=c["params"]; mask = _mask_range(df[cname], p.get("min"), p.get("max"))
        elif ctype == "enum" and cname in df.columns:
            p=c["params"]; mask = _mask_enum(df[cname], p.get("allowed", []))
        elif ctype == "null_rate" and cname in df.columns:
            mask = df[cname].isna()
        elif ctype == "freshness" and cname in df.columns:
            p=c["params"]; mask = _mask_freshness(df[cname], p.get("max_age_days"), p.get("parse_format"))
        if mask is not None:
            df.loc[mask].head(200).to_csv(fpath, index=False)
            failure_samples[c["name"]] = fpath.name

    # FIX PIPELINE
    cleaned_path = out_dir / "cleaned.csv"
    fix_report_path = out_dir / "fix_report.json"
    quarantine_dir = out_dir / "quarantine"
    if args.fix or args.fix_dry_run:
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        report = FixReport()
        report.total_rows_before = int(len(df))

        for table in rules.get("tables", []):
            tname = table.get("name", "table")
            df = trim_strings(df, [c for c in df.columns], report, tname)
            for chk in table.get("checks", []):
                if chk.get("type") == "duplicate":
                    subset = chk.get("subset")
                    df = drop_exact_duplicates(df, subset=subset, report=report, table_name=tname, quarantine_dir=quarantine_dir)
            for col in table.get("columns", []):
                cname = col.get("name")
                for chk in col.get("checks", []):
                    ctype = chk.get("type")
                    if ctype == "range":
                        df = clip_range(df, column=cname, min_val=chk.get("min"), max_val=chk.get("max"), report=report, table_name=tname, quarantine_dir=quarantine_dir)
                    elif ctype == "enum":
                        allowed = chk.get("allowed")
                        if isinstance(allowed, list):
                            df = enforce_enum(df, column=cname, allowed=allowed, report=report, table_name=tname, quarantine_dir=quarantine_dir)
                    elif ctype == "null_rate" and "fill_value" in chk:
                        df = fill_nulls(df, column=cname, fill_value=chk.get("fill_value"), report=report, table_name=tname)
                    elif ctype == "freshness":
                        fmt = chk.get("parse_format")
                        df = parse_dates(df, column=cname, fmt=fmt, report=report, table_name=tname, quarantine_dir=quarantine_dir)

        report.total_rows_after = int(len(df))

        # Guardrails
        if report.total_rows_before and report.total_rows_before > 0:
            delta = report.total_rows_before - report.total_rows_after
            impact_pct = 100.0 * (delta / report.total_rows_before)
            if impact_pct > args.max_impact_pct:
                raise SystemExit(f"Fix impact {impact_pct:.2f}% exceeds --max-impact-pct {args.max_impact_pct:.2f}%")

            rep = report.to_dict()
            cell_changes = sum(a.get("affected", 0) for a in rep.get("actions", []) if a.get("action") != "drop_duplicates")
            total_cells = int(report.total_rows_before * len(df.columns))
            if total_cells:
                cell_pct = 100.0 * (cell_changes / total_cells)
                if cell_pct > args.max_cell_changes_pct:
                    raise SystemExit(f"Cell changes {cell_pct:.2f}% exceed --max-cell-changes-pct {args.max_cell_changes_pct:.2f}%")
            with fix_report_path.open("w", encoding="utf-8") as fp:
                json.dump(rep, fp, indent=2)

        if args.fix and not args.fix_dry_run:
            df.to_csv(cleaned_path, index=False)

    # Viz data (null heatmap)
    viz = None
    if args.viz == "on":
        import pandas as _pd
        null_cols = [c["column"] for c in checks if c["type"]=="null_rate" and c["status"]=="fail" and c.get("column")]
        if not null_cols:
            head = df.head(1000)
            fracs = head.isna().mean().sort_values(ascending=False)
            null_cols = [c for c in fracs.index.tolist() if fracs[c] > 0.0]
        null_cols = [c for c in null_cols if c in df.columns][:14]
        sample = df.head(10).copy()
        grid = []
        for _, row in sample.iterrows():
            grid.append([1 if _pd.isna(row[c]) else 0 for c in null_cols])
        viz = {"null_heatmap": {"cols": null_cols, "grid": grid}}

    evaluation = {
        "source": src,
        "passed": int(passed),
        "failed": int(failed),
        "checks": checks,
        "failure_samples": failure_samples,
    }
    if viz is not None:
        evaluation["viz"] = viz

    results_path = out_dir / "results.json"
    with results_path.open("w", encoding="utf-8") as fp:
        json.dump(evaluation, fp, indent=2)
    print(f"Wrote {results_path}")

if __name__ == "__main__":
    main()
