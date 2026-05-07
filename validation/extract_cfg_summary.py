#!/usr/bin/env python3
"""
extract_cfg_summary.py
Converts Cobol-REKT cfg-{PROG}.cbl.json -> validation/structure/{PROG}_cfg.json
Also parses app/cbl/{PROG}.cbl DATA DIVISION for Level-01 data items.

Usage:
    py validation/extract_cfg_summary.py CBACT04C
    py validation/extract_cfg_summary.py --all
"""

import json
import hashlib
import re
import sys
from pathlib import Path

ROOT       = Path(__file__).parent.parent
REKT_DIR   = ROOT / "validation" / "rekt"
STRUCT_DIR = ROOT / "validation" / "structure"
SRC_DIR    = ROOT / "app" / "cbl"
CFG_TOOL   = "Cobol-REKT smojol-cli + extract_cfg_summary.py"

# Real COBOL paragraph names: uppercase letters, digits, hyphens; no slashes or spaces.
_PARA_RE = re.compile(r'^[A-Z0-9][A-Z0-9\-]{1,}$')

# Exact labels that Cobol-REKT emits as synthetic graph nodes -- never paragraph names.
_SKIP_LABELS = {
    "YES", "NO", "ELSE", "EXIT", "CONTINUE", "UNTIL",
    "END-PERFORM", "END-IF", "END-READ", "END-EVALUATE",
    "END-STRING", "END-COMPUTE", "END-EXEC", "END-CALL",
    "END-SEARCH", "END-UNSTRING", "END-MULTIPLY", "END-DIVIDE",
    "END-ADD", "END-SUBTRACT", "END-RETURN",
}

# COBOL statement verbs -- any CFG node label starting with one of these
# is an inline-code node, never a user paragraph name.
_STMT_PREFIXES = (
    "ACCEPT", "ADD", "CALL", "CLOSE", "COMPUTE", "CONTINUE",
    "DISPLAY", "DIVIDE", "EVALUATE", "EXIT", "GO", "GOBACK",
    "IF", "INITIALIZE", "INSPECT", "MERGE", "MOVE", "MULTIPLY",
    "NEXT", "OPEN", "PERFORM", "READ", "RELEASE", "RETURN",
    "REWRITE", "SEARCH", "SET", "SORT", "STOP", "STRING",
    "SUBTRACT", "UNSTRING", "WRITE",
)

# ---------------------------------------------------------------------------
# Level-01 DATA DIVISION parser
# ---------------------------------------------------------------------------
# COBOL fixed format: cols 1-6 = sequence area, col 7 = indicator
# (* = comment line), cols 8-11 = area A (level numbers live here).
# A Level-01 line looks like:  "       01  ITEM-NAME ..."
#   index 0-5 : sequence area (spaces or digits)
#   index 6   : indicator (space for code, * for comment)
#   index 7+  : "01  NAME"
_L01_RE = re.compile(
    r'^.{6}[^*]\s*01\s+([A-Z0-9][A-Z0-9-]*)(?:\s|\.)'
    , re.IGNORECASE
)
_DATA_DIV_RE = re.compile(r'^\s+DATA\s+DIVISION',     re.IGNORECASE)
_PROC_DIV_RE = re.compile(r'^\s+PROCEDURE\s+DIVISION', re.IGNORECASE)


def extract_l01_items(src_path: Path) -> list:
    """
    Parse a COBOL fixed-format source file and return all Level-01
    data item declarations found in the DATA DIVISION.

    Returns [{"name": str, "level": 1}, ...] in source order, de-duped.
    Items from COPY members are not expanded (only the .cbl source is read).
    """
    if not src_path.exists():
        return []
    items: list = []
    seen: set = set()
    in_data_div = False
    for raw_line in src_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _PROC_DIV_RE.search(raw_line):
            break                          # stop before PROCEDURE DIVISION
        if _DATA_DIV_RE.search(raw_line):
            in_data_div = True
            continue
        if not in_data_div:
            continue
        if len(raw_line) > 6 and raw_line[6] == '*':
            continue                        # skip comment lines
        m = _L01_RE.match(raw_line)
        if m:
            name = m.group(1).upper()
            if name not in seen:
                seen.add(name)
                items.append({"name": name, "level": 1})
    return items


# ---------------------------------------------------------------------------
# Paragraph-node filter
# ---------------------------------------------------------------------------

def is_paragraph_node(label: str) -> bool:
    """True only if label is a user-defined COBOL paragraph name."""
    if '/' in label or ' ' in label:
        return False
    if label in _SKIP_LABELS:
        return False
    if not _PARA_RE.match(label):
        return False
    for prefix in _STMT_PREFIXES:
        if label.startswith(prefix):
            return False
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

def extract(prog_name: str):
    cfg_file = REKT_DIR / f"{prog_name}.cbl.report" / "cfg" / f"cfg-{prog_name}.cbl.json"
    if not cfg_file.exists():
        print(f"[SKIP] No Cobol-REKT output found: {cfg_file}")
        return False

    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data.get("nodes", [])}
    edges = data.get("edges", [])

    out_edges: dict = {}
    for e in edges:
        out_edges.setdefault(e["fromNodeID"], []).append((e["toNodeID"], e["edgeType"]))

    para_nodes = {n["id"]: n for n in nodes.values()
                  if is_paragraph_node(n.get("label", ""))}

    def collect_performs(start_id: str, visited=None) -> list:
        if visited is None:
            visited = set()
        if start_id in visited:
            return []
        visited.add(start_id)
        result: list = []
        for (to_id, _etype) in out_edges.get(start_id, []):
            if to_id in para_nodes:
                lbl = para_nodes[to_id]["label"]
                if lbl not in result:
                    result.append(lbl)
            else:
                for lbl in collect_performs(to_id, visited):
                    if lbl not in result:
                        result.append(lbl)
        return result

    def collect_gotos(start_id: str, visited=None) -> list:
        if visited is None:
            visited = set()
        if start_id in visited:
            return []
        visited.add(start_id)
        result: list = []
        node = nodes.get(start_id, {})
        orig = node.get("originalText", "").upper()
        if "GO TO" in orig:
            for (to_id, _) in out_edges.get(start_id, []):
                if to_id in para_nodes:
                    t = para_nodes[to_id]["label"]
                    if t not in result:
                        result.append(t)
        for (to_id, _) in out_edges.get(start_id, []):
            if to_id not in para_nodes:
                for t in collect_gotos(to_id, visited):
                    if t not in result:
                        result.append(t)
        return result

    root_id = next(
        (nid for nid, n in nodes.items()
         if "ProcedureDivisionBodyContext" in n.get("label", "")),
        None,
    )
    reachable_ids: set = set()
    if root_id:
        stack = [root_id]
        while stack:
            cur = stack.pop()
            if cur in reachable_ids:
                continue
            reachable_ids.add(cur)
            for (to_id, _) in out_edges.get(cur, []):
                stack.append(to_id)

    reachable_paras = {nid for nid in para_nodes if nid in reachable_ids}

    paragraphs = []
    for nid, n in para_nodes.items():
        performs = collect_performs(nid)
        gotos    = collect_gotos(nid)
        paragraphs.append({
            "name":         n["label"],
            "reachable":    nid in reachable_paras,
            "performs":     performs,
            "goto_targets": gotos,
            "goto_flag":    len(gotos) > 0,
        })

    paragraphs.sort(key=lambda p: (not p["reachable"], p["name"]))

    src_file   = SRC_DIR / f"{prog_name}.cbl"
    data_items = extract_l01_items(src_file)

    output = {
        "program_id":  prog_name,
        "source_file": f"app/cbl/{prog_name}.cbl",
        "source_sha":  sha1_file(src_file) if src_file.exists() else "",
        "cfg_tool":    CFG_TOOL,
        "paragraphs":  paragraphs,
        "data_items":  data_items,
    }

    out_file = STRUCT_DIR / f"{prog_name}_cfg.json"
    out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"[OK] {prog_name}: {len(paragraphs)} paragraphs, "
          f"{len(data_items)} L01 items -> {out_file}")
    return True


def main():
    if "--all" in sys.argv:
        for report_dir in sorted(REKT_DIR.glob("*.cbl.report")):
            prog = report_dir.name.replace(".cbl.report", "")
            extract(prog)
    else:
        for prog in sys.argv[1:]:
            extract(prog.replace(".cbl", ""))


if __name__ == "__main__":
    main()
