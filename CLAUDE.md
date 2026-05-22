# Claude Memory

Use this as persistent project memory for agents working in this repository.

## Project Aim

CardDemo is being used as a source corpus for golden-master capture and later
execution comparison against the OS/390 mini-host interpreter. The goal is not
only to run CardDemo on ADCD, but to produce homogeneous evidence that can be
used to implement and validate missing interpreter pieces such as HLASM, LE,
VSAM, CICS, BMS, and batch behavior.

## Canonical Capture Documentation

Read before any golden-master work:

```text
docs/golden-master-capture.md
```

The capture package is:

```text
tools/capture_golden
```

It is importable by other projects through:

```sh
python3 -m pip install -e /path/to/carddemo/tools
```

Do not resurrect the removed wrapper scripts. They were intentionally deleted.
The package and CLI are the contract.

## Current CardDemo State

Working local directory:

```text
/Users/xavi_1/Repositories/carddeom
```

Working remote locations:

```text
/home/xavi/carddemo
/tmp/carddemo
```

ADCD runtime:

```text
Ubuntu host:    configured ADCD Ubuntu host
Container:      zos31-adcd
z/OS FTP/JES:   10.1.1.2:21 from inside container
TN3270 VTAM:    127.0.0.1:2123 from Ubuntu host
CICS:           CICSTS61
CSD:            CICSTS61.DFHCSD
HLQ:            IBMUSER
Volume:         USRVS1
```

Do not assume local Docker is the ADCD runtime.

## Golden Masters Already Captured

Local evidence:

```text
evidence/carddemo-golden
```

Remote Ubuntu evidence:

```text
/home/xavi/carddemo/evidence/carddemo-golden
```

Container evidence:

```text
/tmp/carddemo/evidence/carddemo-golden
```

CICS evidence includes signon, admin menu, user list, user menu, account view,
and card list.

Batch evidence includes final successful spools and exported datasets for:

```text
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

## Important Fixes Already Made

These changes are intentional ADCD compatibility fixes:

- PDS/PDSE allocation in `tools/carddemo_adcd_install.py` enlarged.
- `COMEN01C.cbl` starts with `CBL CICS('SP')` so CICS translation accepts SEND
  PAGE/XCTL usage.
- `CBEXPORT.cbl` and `CBIMPORT.cbl` use sequential file organization for the
  export/import flat files.
- `CBSTM03A.CBL` has fixed fixed-column COBOL source issues.
- `CUSTREC.cpy` has tab/column fixes for fixed COBOL format.
- `MVSWAIT.asm` has a shortened comment for HLASM continuation safety.
- `REPROCT.ctl` contains only the IDCAMS `REPRO` command; IDCAMS did not accept
  the original `/* ... */` comments.
- `CREASTMT.JCL` has corrected volume and a corrupted `SPACE` line fixed.

## Batch Sequencing Memory

CardDemo batch capture must run:

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

The pre-`POSTTRAN` `TRANBKP` is required because `CBTRN02C` opens `TRANSACT`
as output.

`DATEPARM` is required for `TRANREPT`; the package uploads it automatically.
