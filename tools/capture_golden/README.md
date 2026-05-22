# capture-golden

Internal package for capturing CardDemo golden masters from the ADCD environment.

Full repository protocol:

```text
docs/golden-master-capture.md
```

## Install

From another project or workspace:

```sh
python3 -m pip install -e /path/to/carddemo/tools
```

Then import or run it without setting `PYTHONPATH`:

```python
from capture_golden import batch, cics
```

```sh
capture-golden --help
```

For CICS screen capture, install the optional dependency and `s3270` binary:

```sh
python3 -m pip install -e '/path/to/carddemo/tools[cics]'
```

The package name is `capture-golden`; the import name is `capture_golden`.

## Development

You can also run from the repository root without installing:

## CICS screens

Run on the Ubuntu host where `s3270` and `py3270` are installed:

```sh
PYTHONPATH=tools python3 -m capture_golden cics \
  --cics-password "$CICS_PASSWORD" \
  --outdir evidence/carddemo-golden/cics
```

## Batch/JES outputs

Run inside the `zos31-adcd` container so FTPS/JES data channels are stable:

```sh
cd /tmp/carddemo
PYTHONPATH=tools python3 -m capture_golden batch \
  --ftp-pass "$OS390_FTP_PASS" \
  --evidence evidence/carddemo-golden/batch
```

The batch command also uploads `IBMUSER.CARDDEMO.DATEPARM` before running
`TRANREPT`.
