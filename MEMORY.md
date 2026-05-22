# Project Memory

This file is a short human-readable memory index. Detailed procedure lives in
`docs/golden-master-capture.md`; agent-specific instructions live in
`AGENTS.md` and `CLAUDE.md`.

## Canonical Rule

Golden masters must be captured through the importable `capture_golden` package,
not through ad hoc scripts.

## Package

```text
tools/capture_golden
```

Installable from other projects:

```sh
python3 -m pip install -e /Users/xavi_1/Repositories/carddeom/tools
```

CLI:

```sh
capture-golden cics
capture-golden batch
```

Development command:

```sh
PYTHONPATH=tools python3 -m capture_golden
```

## Evidence

Current CardDemo golden masters:

```text
evidence/carddemo-golden
```

The evidence tree contains CICS screen text/HTML and batch spool/dataset
exports. See its README for final job ids and dataset labels.

