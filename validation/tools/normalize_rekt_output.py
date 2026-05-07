#!/usr/bin/env python3
"""
normalize_rekt_output.py
========================
Normalize smojol-cli REKT output from its nested layout to the flat layout
that extract_cfg_summary.py expects.

Background
----------
smojol-cli (as of the build dated 2026-04-30) writes its output into a
nested subdirectory inside --reportDir:

    validation/rekt/<PROG>.cbl.report/<PROG>.CBL.report/cfg/cfg-<PROG>.CBL.json

extract_cfg_summary.py (line 129) expects the flat layout from the original
run convention:

    validation/rekt/<PROG>.cbl.report/cfg/cfg-<PROG>.cbl.json

Schema is IDENTICAL in both layouts (top-level keys: nodes, edges, idProvider).
This script moves files from the nested layout to the flat layout and
lowercases the .CBL. extension in filenames so extract_cfg_summary.py finds
them without modification.

Usage
-----
  # Normalize a single program (run immediately after REKT):
  py validation/tools/normalize_rekt_output.py CBSTM03B

  # Normalize all programs with a nested layout (safe to re-run):
  py validation/tools/normalize_rekt_output.py --all

  # Dry run (show what would move, no files written):
  py validation/tools/normalize_rekt_output.py CBSTM03B --dry-run

Constraints
-----------
- Does NOT modify validation/extract_cfg_summary.py
- Does NOT modify validation/lint_cobol/ or any protected validator
- Does NOT touch COBOL source files
- Safe to re-run: already-flat layouts are skipped ([SKIP])
- Atomic per-program: if inner dir not found, reports [SKIP] and exits cleanly

Exit codes
----------
  0   All targeted programs normalized or already flat.
  1   One or more programs failed during normalization.
"""

import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo layout
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # validation/tools/
REKT_DIR  = _THIS_DIR.parent / "rekt"                # validation/rekt/

# Subdirectories that smojol-cli writes (moved wholesale)
REKT_SUBDIRS = ("cfg", "data_structures", "flow_ast")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def normalize(prog: str, *, dry_run: bool = False) -> str:
    """
    Normalize one program's REKT output from nested to flat layout.

    Returns one of: 'normalized', 'skipped', 'failed'
    """
    prog_upper = prog.upper()
    outer = REKT_DIR / f"{prog_upper}.cbl.report"

    # smojol-cli writes the inner dir with the .CBL (uppercase) suffix
    inner = outer / f"{prog_upper}.CBL.report"

    if not outer.exists():
        print(f"[SKIP]  {prog_upper} — no REKT report directory found: {outer.name}")
        return "skipped"

    if not inner.exists():
        # Check if already flat (prior normalized run or old smojol-cli)
        flat_cfg = outer / "cfg" / f"cfg-{prog_upper}.cbl.json"
        if flat_cfg.exists():
            print(f"[SKIP]  {prog_upper} — already in flat layout")
        else:
            print(f"[SKIP]  {prog_upper} — no nested inner dir and no flat cfg found")
        return "skipped"

    try:
        for sub in REKT_SUBDIRS:
            src_dir = inner / sub
            if not src_dir.exists():
                continue
            dst_dir = outer / sub
            if dry_run:
                for src_file in sorted(src_dir.iterdir()):
                    dst_name = src_file.name.replace(".CBL.", ".cbl.")
                    print(f"  [DRY] MOVE {src_file.relative_to(REKT_DIR)}")
                    print(f"          -> {(dst_dir / dst_name).relative_to(REKT_DIR)}")
                continue
            dst_dir.mkdir(parents=True, exist_ok=True)
            for src_file in src_dir.iterdir():
                # Lowercase .CBL. in filename so extractor glob matches
                dst_name = src_file.name.replace(".CBL.", ".cbl.")
                dst_path = dst_dir / dst_name
                shutil.move(str(src_file), str(dst_path))

        if not dry_run:
            # Remove the now-empty inner directory tree
            shutil.rmtree(inner)
            print(f"[NORMALIZED] {prog_upper}")
        else:
            print(f"[DRY]  {prog_upper} — would normalize (no files written)")

        return "normalized" if not dry_run else "skipped"

    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL]  {prog_upper} — {exc}")
        return "failed"


def find_all_nested() -> list[str]:
    """Return program names whose REKT output is currently in nested layout."""
    results = []
    for outer in sorted(REKT_DIR.glob("*.cbl.report")):
        prog = outer.name.replace(".cbl.report", "").upper()
        inner = outer / f"{prog}.CBL.report"
        if inner.exists():
            results.append(prog)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if "--all" in args:
        targets = find_all_nested()
        if not targets:
            print("[INFO] No programs with nested REKT layout found — nothing to do.")
            return 0
        print(f"[INFO] Found {len(targets)} program(s) with nested layout: {targets}")
    elif args:
        targets = [a.upper() for a in args if not a.startswith("--")]
        if not targets:
            print("[ERROR] No program names provided.")
            return 1
    else:
        print(__doc__)
        return 0

    counts = {"normalized": 0, "skipped": 0, "failed": 0}
    for prog in targets:
        status = normalize(prog, dry_run=dry_run)
        counts[status] = counts.get(status, 0) + 1

    print()
    print("-" * 48)
    print(f"  normalized={counts['normalized']}  "
          f"skipped={counts['skipped']}  "
          f"failed={counts['failed']}")
    print("-" * 48)

    if dry_run:
        print("Dry run complete — no files written.")

    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
