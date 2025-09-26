from __future__ import annotations
import pandas as pd
from typing import Dict, Any, List, Optional, Any

class FixReport:
    def __init__(self) -> None:
        self.actions: List[Dict[str, Any]] = []
        self.total_rows_before: Optional[int] = None
        self.total_rows_after: Optional[int] = None

    def add(self, *, rule: str, table: str, column: str|None, action: str, affected: int, notes: str = "") -> None:
        self.actions.append({
            "rule": rule,
            "table": table,
            "column": column,
            "action": action,
            "affected": int(affected),
            "notes": notes,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows_before": self.total_rows_before,
            "total_rows_after": self.total_rows_after,
            "actions": self.actions,
        }

def trim_strings(df: pd.DataFrame, columns: List[str], report: FixReport, table_name: str) -> pd.DataFrame:
    affected = 0
    for col in columns:
        if col in df.columns and pd.api.types.is_object_dtype(df[col]):
            before = df[col].astype(str)
            after = before.str.strip()
            changed = (before != after)
            affected += int(changed.sum())
            df[col] = after
    if affected:
        report.add(rule=f"{table_name}_trim", table=table_name, column=None, action="trim_strings", affected=affected)
    return df

def drop_exact_duplicates(df: pd.DataFrame, subset: List[str]|None, report: FixReport, table_name: str, quarantine_dir) -> pd.DataFrame:
    subset = subset or df.columns.tolist()
    dup_mask = df.duplicated(subset=subset, keep="first")
    affected = int(dup_mask.sum())
    if affected:
        qpath = quarantine_dir / f"{table_name}_duplicate_rows.csv"
        df.loc[dup_mask].to_csv(qpath, index=False)
        report.add(rule=f"{table_name}_duplicate", table=table_name, column=None, action="drop_duplicates", affected=affected, notes=f"subset={subset}")
        df = df.loc[~dup_mask].copy()
    return df

def clip_range(df: pd.DataFrame, column: str, min_val: float|None, max_val: float|None, report: FixReport, table_name: str, quarantine_dir) -> pd.DataFrame:
    if column not in df.columns:
        return df
    series = pd.to_numeric(df[column], errors="coerce")
    before = series.copy()
    clipped = series.clip(lower=min_val, upper=max_val)
    changed_mask = (before != clipped) & before.notna()
    affected = int(changed_mask.sum())
    if affected:
        qpath = quarantine_dir / f"{table_name}_{column}_range_clipped.csv"
        import pandas as _pd
        _pd.DataFrame({column: before[changed_mask], f"{column}_clipped": clipped[changed_mask]}).to_csv(qpath, index=False)
        report.add(rule=f"{table_name}_{column}_range", table=table_name, column=column, action="clip", affected=affected, notes=f"min={min_val}, max={max_val}")
        df[column] = clipped
    return df

def enforce_enum(df: pd.DataFrame, column: str, allowed: List[Any], report: FixReport, table_name: str, quarantine_dir) -> pd.DataFrame:
    if column not in df.columns:
        return df
    mask_invalid = ~df[column].isin(allowed)
    affected = int(mask_invalid.sum())
    if affected:
        qpath = quarantine_dir / f"{table_name}_{column}_enum_invalid.csv"
        df.loc[mask_invalid, [column]].to_csv(qpath, index=False)
        report.add(rule=f"{table_name}_{column}_enum", table=table_name, column=column, action="quarantine_invalid_enum", affected=affected, notes=f"allowed={allowed}")
    return df

def fill_nulls(df: pd.DataFrame, column: str, fill_value: Any, report: FixReport, table_name: str) -> pd.DataFrame:
    if column not in df.columns:
        return df
    mask = df[column].isna()
    affected = int(mask.sum())
    if affected:
        df.loc[mask, column] = fill_value
        report.add(rule=f"{table_name}_{column}_null_fill", table=table_name, column=column, action="fillna", affected=affected, notes=f"value={fill_value!r}")
    return df

def parse_dates(df: pd.DataFrame, column: str, fmt: str|None, report: FixReport, table_name: str, quarantine_dir) -> pd.DataFrame:
    if column not in df.columns:
        return df
    parsed = pd.to_datetime(df[column], format=fmt, errors="coerce")
    mask_bad = parsed.isna() & df[column].notna()
    affected_bad = int(mask_bad.sum())
    if affected_bad:
        qpath = quarantine_dir / f"{table_name}_{column}_unparsed_dates.csv"
        df.loc[mask_bad, [column]].to_csv(qpath, index=False)
        report.add(rule=f"{table_name}_{column}_date_parse", table=table_name, column=column, action="quarantine_unparsed_dates", affected=affected_bad, notes=f"format={fmt or 'auto'}")
    mask_ok = parsed.notna()
    if int(mask_ok.sum()) > 0:
        df.loc[mask_ok, column] = parsed[mask_ok]
    return df
