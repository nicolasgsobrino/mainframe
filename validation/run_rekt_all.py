#!/usr/bin/env python3
"""
run_rekt_all.py
===============
Batch Cobol-REKT runner for every COBOL source file under app/cbl/.

For each program that does not yet have a REKT report directory the script:
  1. Invokes the smojol-cli JAR with the ``run`` command.
  2. On success immediately runs extract_cfg_summary.py to build the
     validation/structure/<PROG>_cfg.json artefact.

Usage
-----
  py -3 validation/run_rekt_all.py                  # skip already-done
  py -3 validation/run_rekt_all.py --force          # re-run everything
  py -3 validation/run_rekt_all.py --only CBTRN02C CBTRN03C
  py -3 validation/run_rekt_all.py --dry-run        # show commands only
  py -3 validation/run_rekt_all.py --jar path/to/smojol-cli.jar

Environment
-----------
  SMOJOL_JAR    Path to the smojol-cli JAR (overrides --jar and auto-detect).
                If set but the path does not exist, a warning is printed and
                the script falls back to --jar / CANDIDATE_JARS.
  DIALECT_JAR   Path to the dialect-idms JAR (optional; enables IDMS dialect
                support).  Typically:
                  C:\\work\\cobol-rekt\\che-che4z-lsp-for-cobol-integration\\
                    server\\dialect-idms\\target\\dialect-idms.jar
                If set but not found, a warning is printed and the flag is
                omitted from the smojol-cli invocation.

Auto-detect order for the smojol-cli JAR
-----------------------------------------
  1. SMOJOL_JAR environment variable (if the file exists)
  2. --jar CLI argument
  3. Paths listed in CANDIDATE_JARS below (includes the cobol-rekt
     Maven build output at C:\\work\\cobol-rekt\\smojol-cli\\target\\)

Exit codes
----------
  0   All targeted programs produced a report (or were skipped).
  1   One or more programs failed or timed out.
  2   smojol-cli JAR could not be located.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------
ROOT       = Path(__file__).parent.parent.resolve()
SRC_DIR    = ROOT / "app" / "cbl"
REKT_DIR   = ROOT / "validation" / "rekt"
EXTRACT    = ROOT / "validation" / "extract_cfg_summary.py"

# All copybook directories passed to smojol-cli (each becomes a separate
# --copyBooksDir flag).  Order matters: smojol-cli searches them in order.
#   app/cpy       -- application data-structure copybooks
#   app/cpy-bms   -- BMS-generated map copybooks (COUSRxx, COACTxx, etc.)
#   app/cpy-stubs -- CICS system stubs (DFHAID, DFHBMSCA, etc.)
COPY_DIRS = [
    ROOT / "app" / "cpy",
    ROOT / "app" / "cpy-bms",
    ROOT / "app" / "cpy-stubs",
]

# Conventional cobol-rekt checkout location on Windows dev machines.
_COBOL_REKT_ROOT = Path("C:/work/cobol-rekt")

# ---------------------------------------------------------------------------
# Candidate JAR paths (tried in order if env var / --jar not provided)
# ---------------------------------------------------------------------------
CANDIDATE_JARS = [
    # Maven build output in the standard C:\work\cobol-rekt checkout
    _COBOL_REKT_ROOT / "smojol-cli" / "target" / "smojol-cli.jar",
    # Repo-local copies (for offline / bundled setups)
    ROOT / "tools" / "smojol-cli.jar",
    ROOT / "tools" / "cobol-rekt" / "smojol-cli.jar",
    ROOT / "smojol-cli.jar",
    # User home fallbacks
    Path.home() / "tools" / "smojol-cli.jar",
    Path.home() / "cobol-rekt" / "smojol-cli.jar",
]

# Candidate paths for the dialect-idms JAR (auto-detect fallback).
CANDIDATE_DIALECT_JARS = [
    _COBOL_REKT_ROOT
    / "che-che4z-lsp-for-cobol-integration"
    / "server" / "dialect-idms" / "target" / "dialect-idms.jar",
]

# smojol-cli 'run' commands required for CFG + data-structure extraction.
# Each entry becomes its own --commands TOKEN on the command line because
# smojol-cli's picocli binding does not split on commas.
# Order matters: WRITE_FLOW_AST must precede WRITE_CFG.
REKT_COMMANDS = [
    "WRITE_FLOW_AST",
    "WRITE_CFG",
    "WRITE_DATA_STRUCTURES",
]

# Default per-program timeout in seconds (5 minutes).
DEFAULT_TIMEOUT = 300

# ANSI colour helpers (disabled on Windows unless TERM is set)
_USE_COLOR = sys.stdout.isatty() and os.environ.get("TERM", "dumb") != "dumb"

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

OK   = lambda t: _c("32", t)   # green
FAIL = lambda t: _c("31", t)   # red
SKIP = lambda t: _c("33", t)   # yellow
INFO = lambda t: _c("36", t)   # cyan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_sources() -> list[Path]:
    """Return all .cbl / .CBL files in app/cbl/, sorted by name."""
    return sorted(
        p for p in SRC_DIR.iterdir()
        if p.suffix.lower() == ".cbl"
    )


def prog_name(src: Path) -> str:
    """CBACT01C  from  app/cbl/CBACT01C.cbl"""
    return src.stem.upper()


def report_dir(prog: str) -> Path:
    return REKT_DIR / f"{prog}.cbl.report"


def cfg_json(prog: str) -> Path:
    return ROOT / "validation" / "structure" / f"{prog}_cfg.json"


def locate_jar(jar_arg: str | None) -> Path | None:
    """
    Return the smojol-cli JAR path, searching in priority order:
      1. SMOJOL_JAR env var  (warn + fall through if path missing)
      2. --jar CLI argument  (error if given but missing)
      3. CANDIDATE_JARS list
    Returns None only when every option is exhausted.
    """
    env = os.environ.get("SMOJOL_JAR")
    if env:
        p = Path(env)
        if p.exists():
            return p
        # Warn but do NOT return -- fall through to --jar and candidates.
        print(FAIL(f"[JAR] SMOJOL_JAR points to missing file: {p} -- trying fallbacks"))

    if jar_arg:
        p = Path(jar_arg)
        if p.exists():
            return p
        print(FAIL(f"[JAR] --jar path not found: {p}"))
        return None

    for candidate in CANDIDATE_JARS:
        if candidate.exists():
            return candidate

    return None


def locate_dialect_jar() -> Path | None:
    """
    Return the dialect-idms JAR path.
    Checks DIALECT_JAR env var first, then CANDIDATE_DIALECT_JARS.
    Returns None (and prints a warning) if the env var is set but missing.
    """
    env = os.environ.get("DIALECT_JAR")
    if env:
        p = Path(env)
        if p.exists():
            return p
        print(FAIL(f"[JAR] DIALECT_JAR points to missing file: {p} -- trying fallbacks"))

    for candidate in CANDIDATE_DIALECT_JARS:
        if candidate.exists():
            return candidate

    return None


def build_rekt_cmd(jar: Path, src: Path, prog: str) -> list[str]:
    """
    Build the smojol-cli invocation for a single program.

    smojol-cli expects each command as a separate --commands flag:
      java -jar smojol-cli.jar run <filename.cbl>
           --commands WRITE_FLOW_AST
           --commands WRITE_CFG
           --commands WRITE_DATA_STRUCTURES
           --srcDir       <app/cbl>
           --copyBooksDir <app/cpy>
           --copyBooksDir <app/cpy-bms>
           --copyBooksDir <app/cpy-stubs>
           --dialectJarPath <dialect-idms.jar>   # omitted when not found
           --dialect      COBOL
           --reportDir    validation/rekt/<PROG>.cbl.report
           --generation=PARAGRAPH

    NOTE: We pass only the filename (src.name) rather than the full absolute
    path.  smojol-cli resolves the file relative to --srcDir internally, and
    its case-sensitive path matching fails on Windows when given a full path.
    """
    out = report_dir(prog)
    cmd = [
        "java", "-jar", str(jar),
        "run", src.name,          # filename only, not full absolute path
    ]

    # Each command is a separate --commands flag -- do NOT join with commas.
    for rekt_cmd in REKT_COMMANDS:
        cmd += ["--commands", rekt_cmd]

    cmd += ["--srcDir", str(SRC_DIR)]

    # Add each copybook directory as a separate --copyBooksDir flag.
    for cpy_dir in COPY_DIRS:
        if cpy_dir.exists():
            cmd += ["--copyBooksDir", str(cpy_dir)]

    dialect_jar = locate_dialect_jar()
    if dialect_jar:
        cmd += ["--dialectJarPath", str(dialect_jar)]

    cmd += [
        "--dialect",    "COBOL",
        "--reportDir",  str(out),
        "--generation=PARAGRAPH",
    ]
    return cmd


def run_extract(prog: str, dry_run: bool) -> bool:
    """Run extract_cfg_summary.py for a single program."""
    cmd = [sys.executable, str(EXTRACT), prog]
    if dry_run:
        print(INFO(f"  [DRY] {' '.join(cmd)}"))
        return True
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Per-program runner
# ---------------------------------------------------------------------------

def run_program(
    jar: Path,
    src: Path,
    *,
    force: bool,
    dry_run: bool,
    timeout: int,
) -> str:
    """
    Run REKT + extract for one program.
    Returns one of: 'skipped', 'ok', 'failed', 'timeout', 'dry'
    """
    prog = prog_name(src)
    rdir = report_dir(prog)

    if not force and rdir.exists() and cfg_json(prog).exists():
        print(SKIP(f"[SKIP] {prog}: report + cfg.json already exist"))
        return "skipped"

    cmd = build_rekt_cmd(jar, src, prog)

    if dry_run:
        print(INFO(f"[DRY]  {prog}"))
        print(INFO(f"       {' '.join(cmd)}"))
        run_extract(prog, dry_run=True)
        return "dry"

    rdir.mkdir(parents=True, exist_ok=True)
    print(INFO(f"[REKT] {prog}  ({src.stat().st_size // 1024} KB) ..."))

    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            timeout=timeout,
            capture_output=False,  # let REKT output flow to console
        )
    except subprocess.TimeoutExpired:
        print(FAIL(f"[TIMEOUT] {prog}: exceeded {timeout}s"))
        return "timeout"
    except FileNotFoundError:
        print(FAIL("[ERROR] 'java' not found on PATH. Is the JDK installed?"))
        return "failed"

    if result.returncode != 0:
        print(FAIL(f"[FAIL] {prog}: smojol-cli exited {result.returncode}"))
        return "failed"

    print(OK(f"[REKT-OK] {prog}: report written to {rdir.relative_to(ROOT)}"))

    ok = run_extract(prog, dry_run=False)
    if ok:
        print(OK(f"[CFG-OK]  {prog}: cfg.json written"))
        return "ok"
    else:
        print(FAIL(f"[CFG-FAIL] {prog}: extract_cfg_summary.py failed"))
        return "failed"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> dict:
    args = sys.argv[1:]
    opts = {
        "force":   False,
        "dry_run": False,
        "jar":     None,
        "only":    [],
        "timeout": DEFAULT_TIMEOUT,
    }
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--force":
            opts["force"] = True
        elif a == "--dry-run":
            opts["dry_run"] = True
        elif a == "--skip-existing":   # default; accepted for clarity
            pass
        elif a == "--jar":
            i += 1
            opts["jar"] = args[i]
        elif a == "--timeout":
            i += 1
            opts["timeout"] = int(args[i])
        elif a == "--only":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                opts["only"].append(args[i].upper())
                i += 1
            continue
        elif a in ("--help", "-h"):
            print(textwrap.dedent(__doc__).strip())
            sys.exit(0)
        i += 1
    return opts


def main() -> int:
    opts = parse_args()

    # ---- locate JAR -------------------------------------------------
    if not opts["dry_run"]:
        jar = locate_jar(opts["jar"])
        if jar is None:
            print(FAIL("[ERROR] Cannot locate smojol-cli JAR."))
            print(FAIL("        Set SMOJOL_JAR env var or use --jar PATH."))
            searched = [str(p) for p in CANDIDATE_JARS]
            print(FAIL(f"        Searched: {searched}"))
            return 2
        print(INFO(f"[JAR]  Using: {jar}"))

        dialect_jar = locate_dialect_jar()
        if dialect_jar:
            print(INFO(f"[JAR]  Dialect: {dialect_jar}"))
        else:
            print(INFO("[JAR]  Dialect JAR not found; --dialectJarPath will be omitted"))
    else:
        jar = Path("smojol-cli.jar")   # placeholder for dry-run display

    # ---- gather sources ---------------------------------------------
    sources = find_sources()
    if opts["only"]:
        sources = [s for s in sources if prog_name(s) in opts["only"]]
        if not sources:
            print(FAIL(f"[ERROR] --only matched no files: {opts['only']}"))
            return 1

    print(INFO(f"[INFO] {len(sources)} source file(s) targeted"))
    print()

    # ---- run --------------------------------------------------------
    results: dict[str, str] = {}
    for src in sources:
        status = run_program(
            jar, src,
            force=opts["force"],
            dry_run=opts["dry_run"],
            timeout=opts["timeout"],
        )
        results[prog_name(src)] = status
        print()

    # ---- summary ----------------------------------------------------
    col_w = max(len(p) for p in results) + 2
    print("-" * 56)
    print(f"{'Program':<{col_w}}  Status")
    print("-" * 56)
    counts: dict[str, int] = {"ok": 0, "skipped": 0, "failed": 0, "timeout": 0, "dry": 0}
    for prog, status in sorted(results.items()):
        counts[status] = counts.get(status, 0) + 1
        if status == "ok":
            line = OK(f"  {'PASS':<10}")
        elif status == "skipped":
            line = SKIP(f"  {'SKIP':<10}")
        elif status == "dry":
            line = INFO(f"  {'DRY':<10}")
        else:
            line = FAIL(f"  {'FAIL':<10}")
        print(f"{prog:<{col_w}}{line}")
    print("-" * 56)
    print(
        f"  ok={counts['ok']}  skipped={counts['skipped']}  "
        f"failed={counts['failed']}  timeout={counts['timeout']}"
    )
    print("-" * 56)

    if counts["failed"] or counts["timeout"]:
        print(FAIL("\nOne or more programs failed. See output above."))
        print(FAIL("After fixing, re-run:  py -3 validation/run_rekt_all.py --only <PROG>"))
        return 1

    if opts["dry_run"]:
        print(INFO("\nDry run complete -- no files written."))

    return 0


if __name__ == "__main__":
    sys.exit(main())
