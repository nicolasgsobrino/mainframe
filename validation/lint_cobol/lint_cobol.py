#!/usr/bin/env python3
"""
Layer 2 — COBOL Source Lint Runner

Runs all lint rules in rules/ against every .cbl/.CBL file in app/cbl/.
Emits a JSON report to lint_results/lint_results.json and a console summary.

Usage:
    py -3 validation/lint_cobol/lint_cobol.py
    py -3 validation/lint_cobol/lint_cobol.py --only COCRDLIC
    py -3 validation/lint_cobol/lint_cobol.py --fail-on-error

Exit codes:
    0  All files pass all rules (or --fail-on-error not set)
    1  One or more ERROR-severity findings with --fail-on-error
"""

import argparse
import glob
import importlib.util
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT  = Path(__file__).resolve().parents[2]
CBL_DIR    = REPO_ROOT / "app" / "cbl"
RULES_DIR  = Path(__file__).parent / "rules"
RESULTS_DIR = Path(__file__).parent / "lint_results"


def load_rules():
    """Dynamically load every Lxxx_*.py module from rules/."""
    rules = []
    for path in sorted(RULES_DIR.glob("L*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rules.append(mod)
    return rules


def collect_sources(only=None):
    """Return list of (name, path) tuples for .cbl files to scan."""
    sources = []
    for p in sorted(CBL_DIR.glob("*.cbl")) + sorted(CBL_DIR.glob("*.CBL")):
        name = p.stem.upper()
        if only and name != only.upper():
            continue
        sources.append((name, p))
    return sources


def run_rule(rule_mod, name, lines):
    """Call rule_mod.check(name, lines) — returns list of finding dicts."""
    try:
        findings = rule_mod.check(name, lines)
        return findings or []
    except Exception as exc:
        return [{
            "rule":     rule_mod.RULE_ID,
            "severity": "ERROR",
            "file":     name,
            "line":     0,
            "message":  f"Rule crashed: {exc}"
        }]


def main():
    parser = argparse.ArgumentParser(description="COBOL Source Linter — Layer 2")
    parser.add_argument("--only",          help="Lint a single program (e.g. COCRDLIC)")
    parser.add_argument("--fail-on-error", action="store_true",
                        help="Exit 1 if any ERROR-severity finding exists")
    args = parser.parse_args()

    rules   = load_rules()
    sources = collect_sources(only=args.only)

    if not sources:
        print(f"[lint_cobol] No sources found in {CBL_DIR}")
        sys.exit(0)

    all_findings = []
    file_summary = {}

    for name, path in sources:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        file_findings = []
        for rule in rules:
            file_findings.extend(run_rule(rule, name, lines))
        all_findings.extend(file_findings)

        errors   = sum(1 for f in file_findings if f["severity"] == "ERROR")
        warnings = sum(1 for f in file_findings if f["severity"] == "WARNING")
        info     = sum(1 for f in file_findings if f["severity"] == "INFO")
        status   = "PASS" if errors == 0 else "FAIL"
        file_summary[name] = {"status": status, "errors": errors,
                               "warnings": warnings, "info": info}
        icon = "[OK]" if status == "PASS" else "[X]"
        print(f"{icon}  {name:<20}  {status}  E={errors} W={warnings} I={info}")

    # --- Console detail for failures ---
    failures = [f for f in all_findings if f["severity"] == "ERROR"]
    if failures:
        print("\n── ERROR Details ─────────────────────────────────")
        for f in failures:
            loc = f"line {f['line']}" if f.get("line") else ""
            print(f"  [{f['rule']}] {f['file']} {loc}: {f['message']}")

    # --- JSON report ---
    RESULTS_DIR.mkdir(exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": 2,
        "summary": {
            "total_files": len(sources),
            "total_errors": len(failures),
            "total_warnings": sum(1 for f in all_findings if f["severity"] == "WARNING"),
            "total_info": sum(1 for f in all_findings if f["severity"] == "INFO"),
        },
        "files": file_summary,
        "findings": all_findings,
    }
    out_path = RESULTS_DIR / "lint_results.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n[lint_cobol] Report written -> {out_path}")
    print(f"[lint_cobol] Total: {len(sources)} files | "
          f"{report['summary']['total_errors']} errors | "
          f"{report['summary']['total_warnings']} warnings")

    if args.fail_on_error and failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
