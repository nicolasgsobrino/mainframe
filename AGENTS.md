# Agent Instructions

This repository contains AWS CardDemo adapted for the ADCD Ubuntu environment
and a reusable golden-master capture package.

## Golden Master Rule

All new corpus capture work must follow:

```text
docs/golden-master-capture.md
```

The only supported capture interface is the importable package:

```text
tools/capture_golden
```

Do not add standalone capture scripts. If a new behavior is needed, add it to
the package or to an importable module that uses the package.

## Current Environment

Known working ADCD setup:

```text
Local repo:       /Users/xavi_1/Repositories/carddeom
Ubuntu host repo: /home/xavi/carddemo
Container repo:   /tmp/carddemo
ADCD container:   zos31-adcd
CICS region:      CICSTS61
HLQ:              IBMUSER
Volume:           USRVS1
```

Run CICS/TN3270 capture on the Ubuntu host. Run batch/JES capture inside
`zos31-adcd`.

## Commands

From repo root without installing:

```sh
PYTHONPATH=tools python3 -m capture_golden --help
```

CICS capture:

```sh
cd /home/xavi/carddemo
PYTHONPATH=tools python3 -m capture_golden cics \
  --cics-password "$CICS_PASSWORD" \
  --outdir evidence/carddemo-golden/cics
```

Batch capture:

```sh
docker exec zos31-adcd sh -lc '
  cd /tmp/carddemo &&
  PYTHONPATH=tools python3 -m capture_golden batch \
    --ftp-pass "$OS390_FTP_PASS" \
    --evidence evidence/carddemo-golden/batch
'
```

## Validation

Before saying a capture is complete:

- Check final JES RCs.
- Confirm exported datasets exist.
- Confirm CICS login still reaches the CardDemo menu after batch.
- Copy evidence back to local `evidence/<corpus>-golden`.
- Update the corpus README.

## Caution

`py3270` can be unreliable when screens do not report input fields cleanly. It
is acceptable to replace the CICS backend with direct `s3270` inside
`capture_golden`, but do not add external one-off scripts.
