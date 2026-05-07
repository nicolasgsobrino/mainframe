#!/usr/bin/env python3
"""
pass3_synthesize.py — Pass 3 semantic synthesis payload emitter.

Task: T-2026-04-23-002
Plan: AIFIRST-PLAN-3PASS.md §6 + §15 (Rules 8 & 10)
Contract: .aifirst/runs/T-2026-04-23-002/translation-prompt-contract-v2.md

Pass 3 synthesizes Pass-2 propositions into paragraph-scoped
`logical_groups[]` and `business_rules[]` entries for the final v1.1 MD.
One LLM request is emitted per paragraph that has \u22651 proposition;
paragraphs with all-TEMPLATE propositions of a trivial shape (single
sequential MOVE) can be collapsed by the dispatcher, but this emitter
does not filter \u2014 it emits one payload per non-empty paragraph so the
audit manifest is exhaustive.

Output: validation/pass3/<PROGRAM_ID>_synth_requests.jsonl
  One JSONL line per paragraph, Rule-8 envelope (temperature=0, seed=42,
  response_format=json_object, max_tokens bounded).

No endpoint is called in this sandbox (Risk Flag RF-03). The payload
file is the audit artifact. A human operator dispatches the payloads
out-of-band, collects responses into:

    validation/pass3/<PROGRAM_ID>_synth_responses.jsonl

\u2026 which are merged by a separate tool into
`translations/baseline-v1.1/<PROGRAM_ID>.md` under `logical_groups[]`
and `business_rules[]`.

Rule 10 enforcement: every `semantic_pattern` value in the response MUST
come from the 9-value enum (see SEMANTIC_PATTERN_ENUM). `unknown` is
permitted only as a deliberate admission that requires human annotation
before merge; it is a blocking T-PASS3-SEMANTIC failure in
`validate_pass3.py` until reclassified.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

SEMANTIC_PATTERN_ENUM = [
    "guard-with-override",
    "accumulation",
    "state-machine",
    "delegation",
    "sequential",
    "conditional-branch",
    "cics-interaction",
    "file-io",
    "unknown",
]

SYSTEM_PROMPT = (
    "You are a COBOL-to-English semantic synthesizer. Given an ordered "
    "list of Pass-2 propositions belonging to a single paragraph, produce "
    "a paragraph-level summary in the structured JSON format below. "
    "Respond with ONLY the JSON object \u2014 no prose, no code fence, no "
    "commentary.\n\n"
    "Required response JSON schema:\n"
    "{\n"
    '  "paragraph": "<copy from request>",\n'
    '  "group_label": "<short human-readable label, 2-5 words>",\n'
    '  "semantic_pattern": "<one of: ' + ", ".join(SEMANTIC_PATTERN_ENUM) + '>",\n'
    '  "summary": "<one-sentence paragraph-level description>",\n'
    '  "member_seqs": [<int>, ...],\n'
    '  "business_rules": [\n'
    '    {"id": "BR-NNN", "rule": "<English statement>", "rule_type": '
    '"<guard|transform|lookup|audit|display>", "confidence": "<high|medium|low>"}\n'
    "  ]\n"
    "}\n\n"
    "Rule 10: `semantic_pattern` MUST be one of the nine enum values. "
    "`unknown` is permitted ONLY when the paragraph is genuinely "
    "unclassifiable; it triggers a human-review gate and blocks merge. "
    "Do NOT use `unknown` as a default \u2014 prefer `sequential` for linear "
    "flows and `conditional-branch` for IF/EVALUATE gating.\n"
    "Rule 9: all data names in business_rules[].rule text must be fully "
    "qualified if the underlying Pass-2 proposition carries a qualified name."
)


def group_by_paragraph(propositions: list[dict]) -> "OrderedDict[str, list[dict]]":
    """Preserve first-seen order so CFG order is respected in the output."""
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for p in propositions:
        groups.setdefault(p["paragraph"], []).append(p)
    return groups


def build_user_prompt(paragraph: str, props: list[dict], program_id: str) -> str:
    lines = [
        f"Program ID: {program_id}",
        f"Paragraph: {paragraph}",
        f"Proposition count: {len(props)}",
        "",
        "Ordered propositions (seq \u2192 verb \u2192 proposition):",
    ]
    for p in props:
        verb = p["verb"]
        # Prefer final proposition; fall back to PARTIAL stub for display purposes
        # (the stub is clearly marked in the prompt text).
        prop_text = p.get("proposition")
        if prop_text is None:
            if p.get("proposition_source") == "PARTIAL":
                prop_text = f"(PARTIAL stub, unrefined) {p.get('proposition_stub')!r}"
            else:
                prop_text = "(LLM refinement pending)"
        ctx = p.get("cfg_branch_context")
        ctx_s = f" [{ctx}]" if ctx else ""
        mod_s = f" [modifies={p['modifies']}]" if p.get("modifies") else ""
        lines.append(f"  seq={p['seq']}  {verb}{ctx_s}{mod_s}  \u2192  {prop_text}")
    lines.append("")
    lines.append(
        "Produce the paragraph-level semantic synthesis per the schema in "
        "the system prompt. Include every proposition's `seq` in `member_seqs`. "
        "Derive business rules ONLY from propositions that carry a real "
        "guard / transform / lookup / audit / display intent \u2014 do not "
        "invent rules for routine MOVE/SET/PERFORM statements."
    )
    return "\n".join(lines)


def build_payload(paragraph: str, props: list[dict], program_id: str,
                  model: str, max_tokens: int) -> dict[str, Any]:
    return {
        "_routing": {
            "task_id": "T-2026-04-23-002",
            "program_id": program_id,
            "paragraph": paragraph,
            "proposition_count": len(props),
            "pass": 3,
        },
        "model": model,
        "temperature": 0,
        "seed": 42,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(paragraph, props, program_id)},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass 3 synthesis request emitter")
    ap.add_argument("--propositions", type=Path, required=True)
    ap.add_argument("--program-id", required=True)
    ap.add_argument("--out", type=Path, required=True,
                    help="Output JSONL file of synthesis request payloads")
    ap.add_argument("--model", default="gpt-4o-2024-08-06")
    ap.add_argument("--max-tokens", type=int, default=900)
    args = ap.parse_args()

    props = json.loads(args.propositions.read_text())
    groups = group_by_paragraph(props)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for para, members in groups.items():
            payload = build_payload(para, members, args.program_id,
                                    args.model, args.max_tokens)
            f.write(json.dumps(payload) + "\n")

    stats = {
        "program_id": args.program_id,
        "total_propositions": len(props),
        "paragraphs": len(groups),
        "synthesis_requests_emitted": len(groups),
        "out": str(args.out),
        "envelope": {
            "temperature": 0,
            "seed": 42,
            "response_format": "json_object",
            "max_tokens": args.max_tokens,
            "model": args.model,
        },
    }
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
