# Golden Master Capture Memory

Agents must use this memory together with `docs/golden-master-capture.md`.

## Non-Negotiables

- Use `tools/capture_golden` as the only capture interface.
- Keep the package importable by other projects.
- Run CICS capture on Ubuntu host.
- Run batch/JES capture inside `zos31-adcd`.
- Capture final evidence into `evidence/<corpus>-golden`.
- Update the corpus README after each successful capture.
- Do not store new passwords in documentation.

## Current CardDemo Commands

CICS:

```sh
cd /home/xavi/carddemo
PYTHONPATH=tools python3 -m capture_golden cics \
  --cics-password "$CICS_PASSWORD" \
  --outdir evidence/carddemo-golden/cics
```

Batch:

```sh
docker exec zos31-adcd sh -lc '
  cd /tmp/carddemo &&
  PYTHONPATH=tools python3 -m capture_golden batch \
    --ftp-pass "$OS390_FTP_PASS" \
    --evidence evidence/carddemo-golden/batch
'
```

## Current Final Evidence

```text
evidence/carddemo-golden
```
