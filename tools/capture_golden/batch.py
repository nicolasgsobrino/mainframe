"""Batch/JES golden-master capture flows."""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

from .zos import ZosConfig, connect, mvs_text, submit_job


BATCH_GOLDEN_JOBS = [
    "CLOSEFIL",
    "DALYREJS",
    "TRANBKP",
    "POSTTRAN",
    "INTCALC",
    "TRANBKP",
    "COMBTRAN",
    "CREASTMT",
    "TRANIDX",
    "TRANREPT",
    "PRTCATBL",
    "OPENFIL",
]

OUTPUT_DATASETS = [
    ("TRANSACT_BKUP_0", "IBMUSER.CARDDEMO.TRANSACT.BKUP(0)", "text"),
    ("SYSTRAN_0", "IBMUSER.CARDDEMO.SYSTRAN(0)", "text"),
    ("TRANSACT_COMBINED_0", "IBMUSER.CARDDEMO.TRANSACT.COMBINED(0)", "text"),
    ("TRANREPT_0", "IBMUSER.CARDDEMO.TRANREPT(0)", "text"),
    ("TCATBALF_REPT", "IBMUSER.CARDDEMO.TCATBALF.REPT", "text"),
    ("STATEMNT_PS", "IBMUSER.CARDDEMO.STATEMNT.PS", "text"),
    ("STATEMNT_HTML", "IBMUSER.CARDDEMO.STATEMNT.HTML", "text"),
]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path, default=Path("evidence/carddemo-golden/batch"))
    parser.add_argument("--hlq", default="IBMUSER")
    parser.add_argument("--volume", default="USRVS1")
    parser.add_argument("--cics-stc", default="CICSTS61")
    parser.add_argument("--cics-load", default="CICSTS61.CICS.SDFHLOAD")
    parser.add_argument("--cics-cob", default="CICSTS61.CICS.SDFHCOB")
    parser.add_argument("--cics-mac", default="CICSTS61.CICS.SDFHMAC")
    parser.add_argument("--cics-samp", default="CICSTS61.CICS.SDFHSAMP")
    parser.add_argument("--cics-csd", default="CICSTS61.DFHCSD")
    parser.add_argument("--coblib", default="IGY.V6R4M0.SIGYCOMP")
    parser.add_argument("--ftp-host", default="10.1.1.2")
    parser.add_argument("--ftp-port", type=int, default=21)
    parser.add_argument("--ftp-user", default="ibmuser")
    parser.add_argument("--ftp-pass", default=os.environ.get("OS390_FTP_PASS", ""))
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-spool", action="store_true")
    parser.add_argument("--jobs", nargs="*", default=BATCH_GOLDEN_JOBS)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2022-07-06")


def build_config(args: argparse.Namespace) -> ZosConfig:
    repo = args.repo.resolve()
    evidence = args.evidence if args.evidence.is_absolute() else repo / args.evidence
    return ZosConfig(
        repo=repo,
        evidence=evidence.resolve(),
        hlq=args.hlq.upper(),
        volume=args.volume.upper(),
        cics_stc=args.cics_stc.upper(),
        cics_load=args.cics_load.upper(),
        cics_cob=args.cics_cob.upper(),
        cics_mac=args.cics_mac.upper(),
        cics_samp=args.cics_samp.upper(),
        cics_csd=args.cics_csd.upper(),
        coblib=args.coblib.upper(),
        ftp_host=args.ftp_host,
        ftp_port=args.ftp_port,
        ftp_user=args.ftp_user,
        ftp_pass=args.ftp_pass,
        timeout=args.timeout,
        purge=not args.keep_spool,
    )


def adapt_carddemo_text(cfg: ZosConfig, text: str) -> str:
    replacements = {
        "AWS.M2": cfg.hlq,
        "AWSHJ1": cfg.volume,
        "TSU023": cfg.volume,
        "SYSAD": "SYSDA",
        "CICSAWSA": cfg.cics_stc,
        "IGY.SIGYCOMP.V63": cfg.coblib,
        "OEM.CICSTS.V05R06M0.CICS.SDFHLOAD": cfg.cics_load,
        "OEM.CICSTS.V05R06M0.CICS.SDFHCOB": cfg.cics_cob,
        "OEM.CICSTS.V05R06M0.CICS.SDFHMAC": cfg.cics_mac,
        "OEM.CICSTS.V05R06M0.CICS.SDFHSAMP": cfg.cics_samp,
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def retrieve_text(cfg: ZosConfig, dsn: str) -> str:
    ftp = connect(cfg)
    try:
        ftp.voidcmd("TYPE A")
        try:
            ftp.sendcmd("SITE SBDATACONN=(IBM-1047,ISO8859-1)")
        except Exception:
            pass
        lines: list[str] = []
        ftp.retrlines(f"RETR '{dsn}'", lines.append)
        return "\n".join(lines) + "\n"
    finally:
        ftp.quit()


def retrieve_binary(cfg: ZosConfig, dsn: str) -> bytes:
    ftp = connect(cfg)
    try:
        ftp.voidcmd("TYPE I")
        data = io.BytesIO()
        ftp.retrbinary(f"RETR '{dsn}'", data.write)
        return data.getvalue()
    finally:
        ftp.quit()


def export_outputs(cfg: ZosConfig, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for label, dsn_template, mode in OUTPUT_DATASETS:
        dsn = dsn_template.replace("IBMUSER", cfg.hlq)
        try:
            if mode == "binary":
                data = retrieve_binary(cfg, dsn)
                path = outdir / f"{label}.bin"
                path.write_bytes(data)
            else:
                text = retrieve_text(cfg, dsn)
                path = outdir / f"{label}.txt"
                path.write_text(text, encoding="utf-8", errors="replace")
            print(f"exported {dsn} -> {path}")
        except Exception as exc:
            path = outdir / f"{label}.missing.txt"
            path.write_text(f"{dsn}: {exc}\n", encoding="utf-8")
            print(f"missing {dsn}: {exc}")


def ensure_dateparm(cfg: ZosConfig, start_date: str, end_date: str) -> None:
    record = f"{start_date} {end_date}"
    mvs_text(cfg, f"{cfg.prefix}.DATEPARM", record)
    print(f"uploaded {cfg.prefix}.DATEPARM = {record}")


def submit_member(cfg: ZosConfig, member: str) -> None:
    path = cfg.repo / "app/jcl" / f"{member}.jcl"
    if not path.exists():
        path = cfg.repo / "app/jcl" / f"{member}.JCL"
    text = adapt_carddemo_text(cfg, path.read_text(encoding="latin-1"))
    submit_job(cfg, f"golden_{member}", text, ok_rc=8)


def run_from_args(args: argparse.Namespace) -> int:
    cfg = build_config(args)
    cfg.evidence.mkdir(parents=True, exist_ok=True)
    ensure_dateparm(cfg, args.start_date, args.end_date)
    for member in args.jobs:
        submit_member(cfg, member)
    export_outputs(cfg, cfg.evidence / "datasets")
    print(f"batch golden evidence in {cfg.evidence}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    return run_from_args(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
