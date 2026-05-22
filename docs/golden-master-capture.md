# Golden Master Capture Protocol

This repository treats golden masters as reproducible evidence, not as ad hoc
screenshots or one-off JES outputs. Every corpus must be captured with the same
shape so it can later be compared against the OS/390 mini-host interpreter.

## Goals

- Capture CICS terminal behavior as stable 3270 screen text plus renderable HTML.
- Capture batch behavior as JES spool plus selected output datasets.
- Record enough environment and sequencing detail to rerun the same capture.
- Keep the capture tooling importable by other projects through `capture_golden`.
- Preserve failed attempts only when they explain a required fix; otherwise keep
  final golden evidence clean.

## Canonical Tooling

The only supported capture interface is the package in `tools/capture_golden`.
Do not add standalone one-off scripts for new corpora.

Install from another project:

```sh
python3 -m pip install -e /path/to/carddemo/tools
```

Run without installation from this repository:

```sh
PYTHONPATH=tools python3 -m capture_golden --help
```

Installed command:

```sh
capture-golden --help
```

Package/import name:

```python
import capture_golden
from capture_golden.zos import ZosConfig
```

Distribution name:

```text
capture-golden
```

## Environment Contract

Current ADCD environment used for CardDemo:

```text
Ubuntu host:        configured ADCD Ubuntu host
Remote repo:        /home/xavi/carddemo
ADCD container:     zos31-adcd
Container repo:     /tmp/carddemo
z/OS FTP/JES:       10.1.1.2:21 from inside container
TN3270 VTAM:        127.0.0.1:2123 from Ubuntu host
CICS APPLID/STC:    CICSTS61
CICS CSD:           CICSTS61.DFHCSD
HLQ:                IBMUSER
Volume:             USRVS1
```

Secrets are operational environment data. Do not document passwords in new
guides; load them from secure local memory, environment variables, or the
operator's mainframe access notes.

## Evidence Layout

Each corpus must write evidence under:

```text
evidence/<corpus-name>-golden/
```

For CardDemo:

```text
evidence/carddemo-golden/
  README.md
  cics/
    cics_001_cc00_signon.txt
    cics_001_cc00_signon.html
    ...
  batch/
    golden_<JOBNAME>_<JOBID>.spool.txt
    datasets/
      <DATASET_LABEL>.txt
```

Rules:

- CICS screen captures must be numbered in execution order.
- CICS captures must include `.txt`; `.html` should be included when using 3270
  tools that can render it.
- Batch spool names must include logical job name and JES job id.
- Exported datasets must use stable labels, not volatile generation names.
- A corpus README must list the final successful jobs and datasets.

## CICS Capture Protocol

Run CICS capture on the Ubuntu host, not inside the ADCD container. The Ubuntu
host has access to the TN3270 port and the 3270 tooling.

Required tools:

```sh
s3270
py3270
```

Current command:

```sh
cd /home/xavi/carddemo
PYTHONPATH=tools python3 -m capture_golden cics \
  --host 127.0.0.1:2123 \
  --applid CICSTS61 \
  --cics-password "$CICS_PASSWORD" \
  --outdir evidence/carddemo-golden/cics
```

For CardDemo the canonical CICS flow is:

```text
1. VTAM menu -> CICSTS61
2. CICS signon
3. CC00 CardDemo signon
4. ADMIN001/PASSWORD -> Admin Menu
5. Option 01 -> User List
6. USER0001/PASSWORD -> Main Menu
7. Option 01 -> Account View
8. Account 00000000001 -> populated Account View
9. Option 03 -> Credit Card List
```

Important terminal notes:

- Prefer deterministic screen text from `Ascii()` over screenshots.
- Treat keyboard lock and protected-field errors as capture bugs, not as app
  behavior.
- CardDemo userid and password fields are both 8 characters; after a full userid
  the terminal auto-tabs, so do not send an extra Tab before the password.
- `py3270` is only a wrapper over `s3270`. If it becomes unreliable for a new
  corpus, implement the backend in `capture_golden` using direct `s3270`
  subprocess commands rather than adding an external script.

## Batch Capture Protocol

Run batch capture inside the `zos31-adcd` container. FTPS/JES data channels are
stable from the container to `10.1.1.2:21`; running the same JES workflow from
the Ubuntu host can hang.

Command:

```sh
docker exec zos31-adcd sh -lc '
  cd /tmp/carddemo &&
  PYTHONPATH=tools python3 -m capture_golden batch \
    --ftp-pass "$OS390_FTP_PASS" \
    --evidence evidence/carddemo-golden/batch
'
```

Current CardDemo batch sequence:

```text
CLOSEFIL
DALYREJS
TRANBKP
POSTTRAN
INTCALC
TRANBKP
COMBTRAN
CREASTMT
TRANIDX
TRANREPT
PRTCATBL
OPENFIL
```

Why this order matters:

- `DALYREJS` defines the reject-file GDG base required by `POSTTRAN`.
- `TRANBKP` before `POSTTRAN` backs up and recreates `TRANSACT` so `CBTRN02C`
  can open it as output.
- `INTCALC` writes `SYSTRAN(+1)`.
- The second `TRANBKP` captures post-posting transaction state.
- `COMBTRAN` combines backed-up transactions with `SYSTRAN`.
- `CREASTMT`, `TRANIDX`, `TRANREPT`, and `PRTCATBL` produce report artifacts.
- `OPENFIL` restores CICS runtime availability after batch closes/redefines
  VSAM resources.

The batch command uploads `IBMUSER.CARDDEMO.DATEPARM` before `TRANREPT`. Default:

```text
2022-01-01 2022-07-06
```

## Return Code Policy

Default acceptable maximum for batch capture is RC 8, but final corpus README
must identify the expected RC for every final job.

For current CardDemo final evidence:

```text
CLOSEFIL   RC=0000
DALYREJS   RC=0000
TRANBKP    RC=0000  pre-posting backup/redefine
POSTTRAN   RC=0004
INTCALC    RC=0000
TRANBKP    RC=0000  post-interest backup/redefine
COMBTRAN   RC=0000
CREASTMT   RC=0000
TRANIDX    RC=0000
TRANREPT   RC=0000
PRTCATBL   RC=0000
OPENFIL    RC=0000
```

If a job fails:

- Read the spool first.
- Fix the root cause in source, JCL, control cards, CSD, or capture sequencing.
- Rerun from the smallest safe checkpoint.
- Keep failed spool only if it documents a known environmental dependency or
  required sequencing rule.
- Do not bless failed output as a golden master.

## Dataset Export Policy

CardDemo exports these final datasets:

```text
TRANSACT_BKUP_0
SYSTRAN_0
TRANSACT_COMBINED_0
TRANREPT_0
TCATBALF_REPT
STATEMNT_PS
STATEMNT_HTML
```

For new corpora, define exported datasets in code as stable logical labels.
Avoid exposing volatile generation numbers in filenames.

Text datasets should be retrieved with z/OS conversion enabled:

```text
TYPE A
SITE SBDATACONN=(IBM-1047,ISO8859-1)
```

Binary datasets must be exported with `TYPE I` and an explicit `.bin` suffix.

## State Reset And Reproducibility

Before capturing a corpus:

- Confirm source commit or local patch set.
- Confirm HLQ and volume.
- Confirm CICS region and CSD.
- Confirm all required PDS/PDSE allocations have enough space.
- Confirm all required CICS files are installed.
- Reset application data to a known baseline with init jobs.
- Record any source/JCL fixes needed for ADCD compatibility.

After capturing:

- Reopen CICS files.
- Validate at least one CICS login after batch.
- Copy evidence from container to Ubuntu and local workspace.
- Delete stale `.missing.txt` markers from earlier partial exports.
- Update the corpus README.

## Extending To New Corpora

For each new corpus:

1. Add a module under `tools/capture_golden/` or a project-specific plugin that
   imports `capture_golden.zos`.
2. Define its CICS flow as named screen captures.
3. Define its batch job order and expected RCs.
4. Define exported datasets by stable logical label.
5. Add a corpus README template.
6. Add any environment-specific adapters in code, not in shell history.
7. Run a clean capture from baseline state.
8. Compare resulting shape against this protocol before treating it as done.

## What Not To Do

- Do not create standalone scripts outside the package.
- Do not use local Docker assumptions; ADCD runs on the Ubuntu host.
- Do not capture arbitrary terminal transcripts as goldens.
- Do not mix failed and final outputs without documenting why.
- Do not rely on manual CICS navigation that is not encoded in the package.
- Do not store new secrets in documentation.
