# Data Quality Sentry (v2)

## Quick Start
```bash
# run from repo
python run_all.py

# with sample data + safe fixes + visuals
python run_all.py --source data/sample.csv --fix --viz on

# or install the CLI
pip install -e .
dqs run --source data/sample.csv --fix --viz on
```

Outputs in `reports/`:
- `index.html` (interactive report with charts + tooltips + sample links)
- `results.json` (checks + viz payload + failure_samples)
- `fix_report.json` and `quarantine/` (when `--fix` is used)
- `failures/*.csv` (per-rule failure samples)

### Rules (checks/rules.yml)
- `null_rate`: supports **max_nulls** and **max_null_frac**
- `freshness`: supports **max_age_days** (unparsable dates are counted as failures)
- `range`, `enum`, table-level `duplicate`

### Guardrails
- `--max-impact-pct` caps % of rows dropped (from dedupe).
- `--max-cell-changes-pct` caps % of cells modified (fill, clip, trim, etc.).

