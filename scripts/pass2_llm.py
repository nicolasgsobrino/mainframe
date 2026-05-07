#!/usr/bin/env python3
"""
pass2_llm.py — Pass 2 LLM request payload emitter (bounded inference).

Task: T-2026-04-23-002
Plan: AIFIRST-PLAN-3PASS.md §5 + §15 (Rule 8)
Contract: .aifirst/runs/T-2026-04-23-002/translation-prompt-contract-v2.md Rule 8

Purpose: for every proposition whose `needs_llm == True` (i.e.
`proposition_source` is `LLM` or `PARTIAL`), build a fully specified LLM
request payload and write the payload set to:

    validation/pass2/<PROGRAM_ID>_llm_requests.jsonl

Each line is a single self-contained JSON payload ready to POST to a
chat-completions endpoint. No endpoint is called in this sandbox — the
payload file is the audit trail (Risk Flag RF-03, same pattern as T-001
`scripts/score_t04.py`). A human operator dispatches the payloads
out-of-band, collects responses into:

    validation/pass2/<PROGRAM_ID>_llm_responses.jsonl

… and re-runs `scripts/pass2_merge.py` (separate tool) to merge refined
propositions back into `<PROGRAM_ID>_propositions.json`.

Rule 8 envelope enforced on every payload:
  - temperature = 0
  - seed = 42
  - response_format = {"type": "json_object"}
  - max_tokens bounded (P4: per-verb, not global flat 400)
  - structured system prompt declaring the required JSON response schema
  - user prompt contains ONLY annotation context (no raw COBOL is
    forwarded except the single statement `raw` string, per prompt
    contract rule "the raw COBOL source must never appear as fenced
    blocks"; a single-statement operand listing is not a program dump)

Review issues addressed:
  #1  PARTIAL entries are routed through this emitter (needs_llm=True)
      so weak template stubs don't ship to Pass 3.
  #2  Every payload includes the annotation `raw` field so the LLM has
      the original statement text.
  #3  Payload files (`*_llm_requests.jsonl`) are emitted to disk here.

Patch history:
  P4 (2026-04-29): Add VERB_MAX_TOKENS per-verb override map.  All
    payloads previously used max_tokens=400 regardless of verb complexity.
    EVALUATE blocks with multiple WHEN arms and EXEC CICS interactions with
    RESP/RESP2 checks regularly exceeded 400 tokens in their JSON response,
    causing truncated JSON that pass2_merge.py rejected, leaving the
    proposition as PARTIAL and re-queuing it.  The fix uses a per-verb
    token budget that scales with expected response complexity while keeping
    the CLI --max-tokens flag as the overrideable default for any verb not
    listed in VERB_MAX_TOKENS.
"""

from __future__ import annotations

import argparse
import json
import sys
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

# P4: Per-verb max_tokens budget.
#
# Rationale for each value:
#   EVALUATE       700  — multiple WHEN arms each generate a clause in the
#                         proposition + reads list; 400 truncates routinely.
#   EXEC CICS      600  — RESP/RESP2 handling, COMMAREA operands, and the
#                         state-machine pattern description all add tokens.
#   EXEC SQL       600  — SQL predicates and INTO operand lists expand output.
#   IF             500  — complex conditions (AND/OR chains) plus ELSE clause.
#   CALL           500  — USING/GIVING argument lists for programs with many
#                         parameters.
#   MOVE CORRESPONDING  500  — group-item field enumeration in reads list.
#
# Any verb NOT listed here uses the CLI --max-tokens default (400 unless
# overridden).  The CLI flag overrides the DEFAULT only; verbs in this map
# always use the map value.  If you need to raise a specific verb budget
# further, update this dict rather than the CLI default.
VERB_MAX_TOKENS: dict[str, int] = {
    "EVALUATE":            700,
    "EXEC CICS":           600,
    "EXEC SQL":            600,
    "IF":                  500,
    "CALL":                500,
    "MOVE CORRESPONDING":  500,
}

SYSTEM_PROMPT = (
    "You are a COBOL-to-English semantic annotator. "
    "Given a single COBOL statement and its surrounding annotation context, "
    "produce a single JSON object that matches the schema below. "
    "Respond with ONLY the JSON object, no prose, no code fence, no commentary. "
    "If any required field cannot be determined, use null (for `modifies`) or "
    "`\"unknown\"` (for `semantic_pattern`); do not fabricate. "
    "\n\nRequired response JSON schema (Rule 8 in translation-prompt-contract-v2.md):\n"
    "{\n"
    '  "seq": <int, copy from request>,\n'
    '  "proposition": "<one-sentence English description, imperative voice>",\n'
    '  "modifies": "<fully-qualified data name OR null>",\n'
    '  "reads": ["<fully-qualified data name>", ...],\n'
    '  "semantic_pattern": "<one of: ' + ", ".join(SEMANTIC_PATTERN_ENUM) + '>",\n'
    '  "confidence": <float in [0.0, 1.0]>\n'
    "}\n"
    "\nRule 9: all data names in `modifies` and `reads` must be fully "
    "qualified (e.g., `WS-REISSUE-DATE OF OUT-REISSUE-DATE-BLOCK`). "
    "Bare unqualified tokens are rejected."
)


def build_user_prompt(prop: dict, program_id: str) -> str:
    lines = [
        f"Program ID: {program_id}",
        f"Paragraph: {prop['paragraph']}",
        f"Source line: {prop['line']}",
        f"Seq (copy this into your response): {prop['seq']}",
        f"Verb: {prop['verb']}",
        f"CFG branch context: {prop.get('cfg_branch_context') or '(none)'}",
        f"Raw statement: {prop.get('raw') or '(unavailable)'}",
    ]
    ops = prop.get("operands") or []
    types = prop.get("operand_types") or []
    if ops:
        lines.append("Operands:")
        for o, t in zip(ops, types):
            lines.append(f"  - {o}  (type={t})")
    if prop.get("proposition_source") == "PARTIAL":
        lines.append(
            f"Template produced a PROVISIONAL stub: {prop.get('proposition_stub')!r}. "
            "Produce the final refined proposition \u2014 do not simply repeat the stub."
        )
    if prop.get("operand_unresolved"):
        lines.append(
            "NOTE: at least one operand could not be resolved against the data-items "
            "inventory during Pass 1. Prefer qualified names per Rule 9; if you "
            "cannot qualify a name, include it verbatim and lower confidence."
        )
    return "\n".join(lines)


def build_payload(prop: dict, program_id: str, model: str,
                  default_max_tokens: int) -> dict[str, Any]:
    """Build a Rule-8-conformant chat-completions payload.

    P4: max_tokens is resolved as:
      1. VERB_MAX_TOKENS[verb]  if the verb has a per-verb budget, else
      2. default_max_tokens     (the CLI --max-tokens value, default 400).
    """
    verb = prop.get("verb", "")
    max_tokens = VERB_MAX_TOKENS.get(verb, default_max_tokens)

    return {
        # Routing keys (not part of the wire payload; stripped by dispatcher).
        "_routing": {
            "task_id": "T-2026-04-23-002",
            "program_id": program_id,
            "seq": prop["seq"],
            "paragraph": prop["paragraph"],
            "line": prop["line"],
            "verb": verb,
            "proposition_source": prop["proposition_source"],
            "max_tokens_used": max_tokens,       # P4: surfaced for audit
            "max_tokens_source": (
                "verb_map" if verb in VERB_MAX_TOKENS else "cli_default"
            ),
        },
        # Wire payload (Rule 8 envelope).
        "model": model,
        "temperature": 0,
        "seed": 42,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(prop, program_id)},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass 2 LLM request payload emitter")
    ap.add_argument("--propositions", type=Path, required=True,
                    help="Pass 2 propositions JSON (from pass2_template.py)")
    ap.add_argument("--program-id", required=True)
    ap.add_argument("--out", type=Path, required=True,
                    help="Output JSONL file of request payloads")
    ap.add_argument("--model", default="gpt-4o-2024-08-06",
                    help="Model ID to set in the payload. Does not call the endpoint.")
    ap.add_argument(
        "--max-tokens", type=int, default=400,
        help=(
            "Default max_tokens for verbs not listed in VERB_MAX_TOKENS. "
            "Verbs with a per-verb budget (EVALUATE, EXEC CICS, etc.) always "
            "use their map value regardless of this flag."
        ),
    )
    args = ap.parse_args()

    propositions = json.loads(args.propositions.read_text())
    targets = [p for p in propositions if p.get("needs_llm")]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for p in targets:
            payload = build_payload(p, args.program_id, args.model, args.max_tokens)
            f.write(json.dumps(payload) + "\n")

    # Per-bucket counts for the audit manifest.
    buckets: dict[str, int] = {}
    for p in targets:
        buckets[p["proposition_source"]] = buckets.get(p["proposition_source"], 0) + 1

    # P4: per-verb token budget breakdown for the audit manifest.
    verb_token_usage: dict[str, int] = {}
    for p in targets:
        verb = p.get("verb", "unknown")
        used = VERB_MAX_TOKENS.get(verb, args.max_tokens)
        verb_token_usage[verb] = max(verb_token_usage.get(verb, 0), used)

    stats = {
        "program_id": args.program_id,
        "total_propositions": len(propositions),
        "llm_requests_emitted": len(targets),
        "buckets": buckets,
        "out": str(args.out),
        "envelope": {
            "temperature": 0,
            "seed": 42,
            "response_format": "json_object",
            "default_max_tokens": args.max_tokens,
            "model": args.model,
            # P4: show the max budget ceiling across all emitted payloads.
            "max_tokens_ceiling": max(verb_token_usage.values()) if verb_token_usage else args.max_tokens,
            "verb_token_budgets": VERB_MAX_TOKENS,
        },
    }
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
