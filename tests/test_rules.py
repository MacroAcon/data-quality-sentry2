"""Unit tests for Data Quality Sentry rules.

These tests exercise the high‑level `run_all.py` entry point by creating
temporary CSV datasets and corresponding rules files, running the checks
via a subprocess and asserting that the expected failures are reported
in the resulting JSON output.

The goal of these tests is to provide confidence that duplicate,
enumeration, range and null rate checks behave as expected.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_and_load(data_csv: str, rules_yaml: str) -> dict:
    """Run the pipeline on the given data and rules, return parsed results.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write data and rules to temporary files
        data_path = Path(tmpdir) / "data.csv"
        rules_path = Path(tmpdir) / "rules.yml"
        out_path = Path(tmpdir) / "out"
        out_path.mkdir(parents=True, exist_ok=True)
        data_path.write_text(data_csv, encoding="utf-8")
        rules_path.write_text(rules_yaml, encoding="utf-8")

        repo_root = Path(__file__).resolve().parents[1]
        cmd = [
            sys.executable,
            str(repo_root / "run_all.py"),
            "--source",
            str(data_path),
            "--rules",
            str(rules_path),
            "--out",
            str(out_path),
            "--viz",
            "off",
        ]
        # Run without fixes; use check=True to raise on failure
        subprocess.run(cmd, check=True)
        # After the run the canonical results.json exists
        res_file = out_path / "results.json"
        assert res_file.exists(), f"results.json was not created at {res_file}"
        return json.loads(res_file.read_text(encoding="utf-8"))


def test_duplicate_detection() -> None:
    """Duplicate check should flag repeated IDs."""
    data = """id,amount\n1,10\n1,15\n2,20\n3,25\n"""
    rules = """
tables:
  - name: test
    checks:
      - type: duplicate
        subset: [id]
    columns: []
"""
    res = _run_and_load(data, rules)
    # Expect exactly one duplicate failure
    dup_checks = [c for c in res["checks"] if c["type"] == "duplicate"]
    assert len(dup_checks) == 1
    assert dup_checks[0]["status"] == "fail"
    assert dup_checks[0]["count"] == 1


def test_enum_validation() -> None:
    """Enum check should flag unexpected values."""
    data = """id,status\n1,new\n2,processing\n3,invalid\n4,shipped\n"""
    rules = """
tables:
  - name: test
    checks: []
    columns:
      - name: status
        checks:
          - type: enum
            allowed: [new, processing, shipped]
"""
    res = _run_and_load(data, rules)
    enum_fail = [c for c in res["checks"] if c["type"] == "enum"]
    assert enum_fail, "No enum check found"
    assert enum_fail[0]["status"] == "fail"
    assert enum_fail[0]["count"] == 1


def test_range_validation() -> None:
    """Range check should flag numbers outside of bounds."""
    data = """id,amount\n1,5\n2,15\n3,25\n4,-3\n"""
    rules = """
tables:
  - name: test
    checks: []
    columns:
      - name: amount
        checks:
          - type: range
            min: 0
            max: 20
"""
    res = _run_and_load(data, rules)
    range_chk = [c for c in res["checks"] if c["type"] == "range"]
    assert range_chk, "No range check found"
    # two values out of range: 25 and -3
    assert range_chk[0]["status"] == "fail"
    assert range_chk[0]["count"] == 2


def test_null_rate() -> None:
    """Null rate check should flag excessive missing values."""
    data = """id,notes\n1,a\n2,\n3,b\n4,\n"""
    rules = """
tables:
  - name: test
    checks: []
    columns:
      - name: notes
        checks:
          - type: null_rate
            max_nulls: 0
"""
    res = _run_and_load(data, rules)
    nr_chk = [c for c in res["checks"] if c["type"] == "null_rate"]
    assert nr_chk, "No null_rate check found"
    assert nr_chk[0]["status"] == "fail"
    # two null values present
    assert nr_chk[0]["count"] == 2