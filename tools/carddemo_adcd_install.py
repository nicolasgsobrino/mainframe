#!/usr/bin/env python3
"""Install and build AWS CardDemo on the remote z/OS 3.1 ADCD.

Run this from the CardDemo repository root inside the remote `zos31-adcd`
container.  The container can reach z/OS FTPD/JES at 10.1.1.2:21; the
Ubuntu host port 2121 is fine for control commands, but its FTPS data channel
is not reliable enough for bulk PDS/data uploads.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import ssl
import sys
import time
from dataclasses import dataclass
from ftplib import FTP_TLS
from pathlib import Path


BASE_BATCH = [
    "CSUTLDTC",
    "COBSWAIT",
    "CBACT01C",
    "CBACT02C",
    "CBACT03C",
    "CBACT04C",
    "CBCUS01C",
    "CBTRN01C",
    "CBTRN02C",
    "CBTRN03C",
    "CBSTM03B",
    "CBSTM03A",
    "CBEXPORT",
    "CBIMPORT",
]

BASE_CICS = [
    "COSGN00C",
    "COMEN01C",
    "COACTVWC",
    "COACTUPC",
    "COCRDLIC",
    "COCRDSLC",
    "COCRDUPC",
    "COTRN00C",
    "COTRN01C",
    "COTRN02C",
    "CORPT00C",
    "COBIL00C",
    "COADM01C",
    "COUSR00C",
    "COUSR01C",
    "COUSR02C",
    "COUSR03C",
]

BASE_BMS = [
    "COSGN00",
    "COMEN01",
    "COACTVW",
    "COACTUP",
    "COCRDLI",
    "COCRDSL",
    "COCRDUP",
    "COTRN00",
    "COTRN01",
    "COTRN02",
    "CORPT00",
    "COBIL00",
    "COADM01",
    "COUSR00",
    "COUSR01",
    "COUSR02",
    "COUSR03",
]

BASE_ASM = ["COBDATFT", "MVSWAIT"]

INIT_JOBS = [
    "DUSRSECJ",
    "CLOSEFIL",
    "ACCTFILE",
    "CARDFILE",
    "CUSTFILE",
    "XREFFILE",
    "TRANFILE",
    "DISCGRP",
    "TCATBALF",
    "TRANCATG",
    "TRANTYPE",
    "OPENFIL",
    "DEFGDGB",
]

DATA_LRECL = {
    "USRSEC.PS": 80,
    "ACCTDATA.PS": 300,
    "ACCDATA.PS": 300,
    "CARDDATA.PS": 150,
    "CUSTDATA.PS": 500,
    "CARDXREF.PS": 50,
    "DALYTRAN.PS.INIT": 350,
    "DALYTRAN.PS": 350,
    "DISCGRP.PS": 50,
    "TRANCATG.PS": 60,
    "TRANTYPE.PS": 60,
    "TCATBALF.PS": 50,
    "EXPORT.DATA.PS": 500,
}


@dataclass
class Config:
    repo: Path
    evidence: Path
    hlq: str
    volume: str
    cics_stc: str
    cics_load: str
    cics_cob: str
    cics_mac: str
    cics_samp: str
    cics_csd: str
    coblib: str
    ftp_host: str
    ftp_port: int
    ftp_user: str
    ftp_pass: str
    timeout: int
    purge: bool

    @property
    def prefix(self) -> str:
        return f"{self.hlq}.CARDDEMO"


def make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("DEFAULT@SECLEVEL=0")
    return ctx


def connect(cfg: Config, jes: bool = False) -> FTP_TLS:
    last_exc: Exception | None = None
    for attempt in range(1, 5):
        ftp = FTP_TLS(context=make_ssl_context(), timeout=cfg.timeout)
        ftp.encoding = "latin-1"
        try:
            ftp.connect(cfg.ftp_host, cfg.ftp_port)
            ftp.auth()
            ftp.prot_p()
            ftp.login(cfg.ftp_user, cfg.ftp_pass)
            if jes:
                ftp.sendcmd("SITE FILETYPE=JES")
                for cmd in ("SITE JESJOBNAME=*", "SITE JESSTATUS=ALL", "SITE JESOWNER=*"):
                    try:
                        ftp.sendcmd(cmd)
                    except Exception:
                        pass
            return ftp
        except Exception as exc:
            last_exc = exc
            try:
                ftp.close()
            except Exception:
                pass
            time.sleep(2 * attempt)
    raise RuntimeError(f"FTP connect failed after retries: {last_exc}")


def list_jobs(cfg: Config) -> dict[str, str]:
    ftp = connect(cfg, jes=True)
    try:
        lines: list[str] = []
        ftp.retrlines("LIST", lines.append)
    finally:
        ftp.quit()
    out: dict[str, str] = {}
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and re.match(r"^(JOB|STC|TSU)\d+$", parts[1]):
            out[parts[1]] = parts[3]
    return out


def submit_job(cfg: Config, name: str, jcl: str, ok_rc: int = 4) -> tuple[str, int, Path]:
    payload = "\n".join(line.rstrip() for line in jcl.splitlines()).rstrip() + "\n"
    ftp = connect(cfg, jes=True)
    try:
        resp = ftp.storlines("STOR SUBMIT", io.BytesIO(payload.encode("ascii", errors="replace")))
    finally:
        ftp.quit()
    m = re.search(r"JOB\d+", resp)
    if not m:
        raise RuntimeError(f"{name}: unexpected JES submit response: {resp!r}")
    job_id = m.group(0)
    deadline = time.time() + cfg.timeout
    while time.time() < deadline:
        if list_jobs(cfg).get(job_id) == "OUTPUT":
            break
        time.sleep(5)
    else:
        raise TimeoutError(f"{name}: {job_id} did not reach OUTPUT within {cfg.timeout}s")

    ftp = connect(cfg, jes=True)
    try:
        lines: list[str] = []
        ftp.retrlines(f"RETR {job_id}", lines.append)
        if cfg.purge:
            try:
                ftp.delete(job_id)
            except Exception:
                pass
    finally:
        ftp.quit()
    spool = "\n".join(lines)
    cfg.evidence.mkdir(parents=True, exist_ok=True)
    spool_path = cfg.evidence / f"{name}_{job_id}.spool.txt"
    spool_path.write_text(spool, encoding="utf-8", errors="replace")
    rc = job_rc(spool)
    print(f"{name}: {job_id} RC={rc} -> {spool_path}")
    if rc > ok_rc:
        raise RuntimeError(f"{name}: {job_id} RC={rc} > {ok_rc}; see {spool_path}")
    return job_id, rc, spool_path


def job_rc(spool: str) -> int:
    ended = list(re.finditer(r"\$HASP395\s+\S+\s+ENDED\s+-\s+RC=(\d+)", spool))
    if ended:
        return max(int(m.group(1)) for m in ended)
    rc = 0
    for m in re.finditer(r"HIGHEST CONDITION CODE WAS\s+(\d+)", spool):
        rc = max(rc, int(m.group(1)))
    for m in re.finditer(r"COND CODE\s+(\d+)", spool):
        rc = max(rc, int(m.group(1)))
    if "ABEND" in spool or "JCL ERROR" in spool:
        rc = max(rc, 16)
    return rc


def mvs_text(cfg: Config, dsn: str, text: str) -> None:
    ftp = connect(cfg)
    try:
        prepare_text_ftp(ftp)
        mvs_text_with_ftp(ftp, dsn, text)
    finally:
        ftp.quit()


def prepare_text_ftp(ftp: FTP_TLS) -> None:
    ftp.voidcmd("TYPE A")
    for cmd in ("SITE SBDATACONN=(IBM-1047,ISO8859-1)", "SITE RECFM=FB LRECL=80 BLKSIZE=0"):
        try:
            ftp.sendcmd(cmd)
        except Exception:
            pass


def mvs_text_with_ftp(ftp: FTP_TLS, dsn: str, text: str) -> None:
    lines = normalize_fb80(text)
    data = ("\n".join(lines) + "\n").encode("latin-1", errors="replace")
    ftp.storlines(f"STOR '{dsn}'", io.BytesIO(data))


def mvs_binary(cfg: Config, dsn: str, path: Path) -> None:
    ftp = connect(cfg)
    try:
        ftp.voidcmd("TYPE I")
        try:
            ftp.sendcmd("SITE FILETYPE=SEQ")
            lrecl = lrecl_for_dsn(dsn)
            ftp.sendcmd(f"SITE RECFM=FB LRECL={lrecl} BLKSIZE=0 TRACKS PRIMARY=5 SECONDARY=5")
        except Exception:
            pass
        mvs_binary_with_ftp(ftp, dsn, path)
    finally:
        ftp.quit()


def mvs_binary_with_ftp(ftp: FTP_TLS, dsn: str, path: Path) -> None:
    with path.open("rb") as fh:
        ftp.storbinary(f"STOR '{dsn}'", fh)


def lrecl_for_dsn(dsn: str) -> int:
    marker = ".CARDDEMO."
    name = dsn.split(marker, 1)[1] if marker in dsn else dsn
    return DATA_LRECL.get(name, 80)


def normalize_fb80(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.expandtabs(8).rstrip("\r\n")
        if len(line) > 80:
            line = line[:80]
        out.append(line)
    return out


def adapt_text(cfg: Config, text: str) -> str:
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


def adapt_proc(cfg: Config, path: Path) -> str:
    text = adapt_text(cfg, path.read_text(encoding="latin-1"))
    if path.name == "BUILDBAT.prc":
        text = text.replace("//BLDBAT PROC", "//BUILDBAT PROC")
    if path.name == "BUILDONL.prc":
        text = text.replace("//BLDONL PROC", "//BUILDONL PROC")
    if path.name == "BUILDBMS.prc":
        text = text.replace(
            "//MAP      EXEC PGM=ASMA90,PARM='SYSPARM(MAP),DECK,NOLOAD'\n",
            "//MAP      EXEC PGM=ASMA90,PARM='SYSPARM(MAP),DECK,NOLOAD'\n"
            "//STEPLIB  DD DSN=ASM.SASMMOD1,DISP=SHR\n"
            "//         DD DSN=ASM.SASMMOD2,DISP=SHR\n",
        )
        text = text.replace(
            "//DSECT    EXEC PGM=ASMA90,PARM='SYSPARM(DSECT),DECK,NOLOAD'\n",
            "//DSECT    EXEC PGM=ASMA90,PARM='SYSPARM(DSECT),DECK,NOLOAD'\n"
            "//STEPLIB  DD DSN=ASM.SASMMOD1,DISP=SHR\n"
            "//         DD DSN=ASM.SASMMOD2,DISP=SHR\n",
        )
    return text


def allocation_jcl(cfg: Config) -> str:
    p = cfg.prefix
    source_pds = ["JCL", "PROC", "PRC.UTIL", "CBL", "CPY", "BMS", "ASM", "MACLIB", "CNTL"]
    listing_pds = ["LST"]
    deletes = [f"{p}.{name}" for name in source_pds + listing_pds]
    deletes.append(f"{p}.LOADLIB")
    for name in DATA_LRECL:
        deletes.append(f"{p}.{name}")

    lines = ["//CDALLOC JOB CLASS=A,MSGCLASS=H,REGION=4M", "//DEL EXEC PGM=IDCAMS",
             "//SYSPRINT DD SYSOUT=*", "//SYSIN DD *"]
    for dsn in deletes:
        lines.append(f"  DELETE {dsn} PURGE")
        lines.append("  IF MAXCC LE 8 THEN SET MAXCC = 0")
    lines.extend(["/*", "//ALLOC EXEC PGM=IEFBR14"])
    pds_space = {
        "CBL": "80,30,120",
        "CPY": "80,30,180",
        "PROC": "40,20,80",
        "PRC.UTIL": "40,20,80",
    }
    for i, name in enumerate(source_pds, 1):
        space = pds_space.get(name, "25,10,80")
        lines.extend(dd_pds(f"S{i:03d}", f"{p}.{name}", "FB", 80, "TRK", space))
    for i, name in enumerate(listing_pds, 1):
        lines.extend(dd_pds(f"L{i:03d}", f"{p}.{name}", "FBA", 133, "CYL", "30,15,200"))
    lines.extend([
        "//LOADLIB DD DSN=" + f"{p}.LOADLIB" + ",",
        "//        DISP=(NEW,CATLG,DELETE),UNIT=3390,",
        "//        VOL=SER=" + cfg.volume + ",SPACE=(CYL,(20,10,80)),",
        "//        DSNTYPE=LIBRARY,DCB=(RECFM=U,BLKSIZE=32760)",
    ])
    for i, (name, lrecl) in enumerate(DATA_LRECL.items(), 1):
        lines.extend(dd_ps(f"D{i:03d}", f"{p}.{name}", lrecl, cfg.volume))
    lines.append("//")
    return "\n".join(lines)


def dd_pds(dd: str, dsn: str, recfm: str, lrecl: int, unit_space: str, space: str) -> list[str]:
    blksize = 27920 if recfm == "FB" and lrecl == 80 else 0
    return [
        f"//{dd:<8} DD DSN={dsn},",
        "//        DISP=(NEW,CATLG,DELETE),UNIT=3390,",
        f"//        SPACE=({unit_space},({space})),",
        f"//        DCB=(DSORG=PO,RECFM={recfm},LRECL={lrecl},BLKSIZE={blksize})",
    ]


def dd_ps(dd: str, dsn: str, lrecl: int, volume: str) -> list[str]:
    return [
        f"//{dd:<8} DD DSN={dsn},",
        "//        DISP=(NEW,CATLG,DELETE),UNIT=3390,",
        f"//        VOL=SER={volume},SPACE=(CYL,(2,2),RLSE),",
        f"//        DCB=(RECFM=FB,LRECL={lrecl},BLKSIZE=0)",
    ]


def upload_sources(cfg: Config) -> None:
    p = cfg.prefix
    ftp = connect(cfg)
    try:
        prepare_text_ftp(ftp)
        upload_dir(cfg, ftp, "app/cbl", f"{p}.CBL", {".cbl", ".CBL"})
        upload_dir(cfg, ftp, "app/cpy", f"{p}.CPY", {".cpy", ".CPY"})
        upload_dir(cfg, ftp, "app/cpy-bms", f"{p}.CPY", {".cpy", ".CPY"})
        upload_dir(cfg, ftp, "app/bms", f"{p}.BMS", {".bms"})
        upload_dir(cfg, ftp, "app/asm", f"{p}.ASM", {".asm"})
        upload_dir(cfg, ftp, "app/maclib", f"{p}.MACLIB", {".mac"})
        upload_dir(cfg, ftp, "app/ctl", f"{p}.CNTL", {".ctl"})
        upload_dir(cfg, ftp, "app/jcl", f"{p}.JCL", {".jcl", ".JCL"})
        for proc in sorted((cfg.repo / "samples/proc").glob("*.prc")):
            member = proc.stem.upper()
            text = adapt_proc(cfg, proc)
            mvs_text_with_ftp(ftp, f"{p}.PROC({member})", text)
            mvs_text_with_ftp(ftp, f"{p}.PRC.UTIL({member})", text)
            print(f"uploaded PROC {member}", flush=True)
        for proc in sorted((cfg.repo / "app/proc").glob("*.prc")):
            member = proc.stem.upper()
            text = adapt_text(cfg, proc.read_text(encoding="latin-1"))
            mvs_text_with_ftp(ftp, f"{p}.PROC({member})", text)
            mvs_text_with_ftp(ftp, f"{p}.PRC.UTIL({member})", text)
            print(f"uploaded app PROC {member}", flush=True)
        for csd in sorted((cfg.repo / "app/csd").glob("*")):
            if csd.is_file() and not csd.name.startswith("."):
                member = csd.stem[:8].upper()
                text = adapt_text(cfg, csd.read_text(encoding="latin-1"))
                mvs_text_with_ftp(ftp, f"{p}.CNTL({member})", text)
                print(f"uploaded CSD {member}", flush=True)
    finally:
        ftp.quit()


def upload_dir(cfg: Config, ftp: FTP_TLS, rel: str, pds: str, suffixes: set[str]) -> None:
    root = cfg.repo / rel
    if not root.exists():
        return
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name.startswith(".") or path.suffix not in suffixes:
            continue
        member = path.stem[:8].upper()
        text = adapt_text(cfg, path.read_text(encoding="latin-1"))
        mvs_text_with_ftp(ftp, f"{pds}({member})", text)
        print(f"uploaded {rel}/{path.name} -> {pds}({member})", flush=True)


def upload_data(cfg: Config) -> None:
    root = cfg.repo / "app/data/EBCDIC"
    ftp = connect(cfg)
    try:
        ftp.voidcmd("TYPE I")
        try:
            ftp.sendcmd("SITE FILETYPE=SEQ")
        except Exception:
            pass
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            dsn = path.name.replace("AWS.M2", cfg.hlq)
            try:
                ftp.sendcmd(f"SITE RECFM=FB LRECL={lrecl_for_dsn(dsn)} BLKSIZE=0 TRACKS PRIMARY=5 SECONDARY=5")
            except Exception:
                pass
            mvs_binary_with_ftp(ftp, dsn, path)
            print(f"uploaded data {path.name} -> {dsn}", flush=True)
    finally:
        ftp.quit()


def asm_job(cfg: Config) -> str:
    p = cfg.prefix
    lines = ["//CDASM JOB CLASS=A,MSGCLASS=H,REGION=4M"]
    for n, mem in enumerate(BASE_ASM, 1):
        lines.extend([
            f"//A{n:03d}    EXEC PGM=ASMA90,PARM='OBJECT,NODECK'",
            "//STEPLIB  DD DSN=ASM.SASMMOD1,DISP=SHR",
            "//         DD DSN=ASM.SASMMOD2,DISP=SHR",
            f"//SYSLIB   DD DSN={p}.MACLIB,DISP=SHR",
            "//         DD DSN=SYS1.MACLIB,DISP=SHR",
            "//         DD DSN=CEE.SCEEMAC,DISP=SHR",
            f"//SYSIN    DD DSN={p}.ASM({mem}),DISP=SHR",
            "//SYSLIN   DD DSN=&&OBJ,DISP=(NEW,PASS),UNIT=3390,",
            "//         SPACE=(TRK,(5,5)),DCB=(RECFM=FB,LRECL=80,BLKSIZE=0)",
            "//SYSPRINT DD SYSOUT=*",
            "//SYSUT1   DD UNIT=3390,SPACE=(CYL,(1,1))",
            "//SYSUT2   DD UNIT=3390,SPACE=(CYL,(1,1))",
            "//SYSUT3   DD UNIT=3390,SPACE=(CYL,(1,1))",
            f"//L{n:03d}    EXEC PGM=HEWL,PARM='LIST,XREF'",
            "//SYSPRINT DD SYSOUT=*",
            f"//SYSLMOD  DD DSN={p}.LOADLIB({mem}),DISP=SHR",
            "//SYSLIN   DD DSN=&&OBJ,DISP=(OLD,DELETE)",
            "//SYSUT1   DD UNIT=3390,SPACE=(CYL,(1,1))",
        ])
    lines.append("//")
    return "\n".join(lines)


def compile_proc_job(cfg: Config, jobname: str, proc: str, parm: str, members: list[str]) -> str:
    lines = [f"//{jobname:<8} JOB CLASS=A,MSGCLASS=H,REGION=0M",
             f"//JCLLIB  JCLLIB ORDER={cfg.prefix}.PROC"]
    for n, mem in enumerate(members, 1):
        step = f"S{n:03d}"
        lines.append(f"//{step:<8} EXEC {proc},{parm}={mem},HLQ={cfg.hlq}")
    lines.append("//")
    return "\n".join(lines)


def build_csd_job(cfg: Config) -> str:
    p = cfg.prefix
    return f"""//CDCSD JOB CLASS=A,MSGCLASS=H,REGION=4M
//STEP1 EXEC PGM=DFHCSDUP
//STEPLIB DD DSN={cfg.cics_load},DISP=SHR
//DFHCSD DD DSN={cfg.cics_csd},DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSIN DD DSN={p}.CNTL(CARDDEMO),DISP=SHR
//"""


def run_init_jobs(cfg: Config) -> None:
    for member in INIT_JOBS:
        source = cfg.repo / "app/jcl" / f"{member}.jcl"
        if not source.exists():
            source = cfg.repo / "app/jcl" / f"{member}.JCL"
        if not source.exists():
            raise FileNotFoundError(member)
        text = adapt_text(cfg, source.read_text(encoding="latin-1"))
        submit_job(cfg, f"init_{member}", text, ok_rc=8)


def run_all(cfg: Config, args: argparse.Namespace) -> None:
    if args.alloc:
        submit_job(cfg, "allocate", allocation_jcl(cfg), ok_rc=4)
    if args.upload:
        upload_sources(cfg)
        upload_data(cfg)
    if args.compile:
        submit_job(cfg, "compile_asm", asm_job(cfg), ok_rc=4)
        submit_job(cfg, "compile_bms", compile_proc_job(cfg, "CDBMS", "BUILDBMS", "MAPNAME", BASE_BMS), ok_rc=4)
        submit_job(cfg, "compile_batch", compile_proc_job(cfg, "CDBATCH", "BUILDBAT", "MEM", BASE_BATCH), ok_rc=4)
        submit_job(cfg, "compile_cics", compile_proc_job(cfg, "CDCICS", "BUILDONL", "MEM", BASE_CICS), ok_rc=4)
    if args.init_vsam:
        run_init_jobs(cfg)
    if args.csd:
        submit_job(cfg, "define_csd", build_csd_job(cfg), ok_rc=4)


def write_manifest(cfg: Config, args: argparse.Namespace) -> None:
    manifest = {
        "repo": str(cfg.repo),
        "hlq": cfg.hlq,
        "prefix": cfg.prefix,
        "volume": cfg.volume,
        "cics_stc": cfg.cics_stc,
        "cics_load": cfg.cics_load,
        "cics_csd": cfg.cics_csd,
        "actions": {
            "alloc": args.alloc,
            "upload": args.upload,
            "compile": args.compile,
            "init_vsam": args.init_vsam,
            "csd": args.csd,
        },
    }
    cfg.evidence.mkdir(parents=True, exist_ok=True)
    (cfg.evidence / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--evidence", type=Path, default=Path("evidence/carddemo-adcd"))
    ap.add_argument("--hlq", default=os.environ.get("CARDDEMO_HLQ", "IBMUSER"))
    ap.add_argument("--volume", default=os.environ.get("CARDDEMO_VOLUME", "USRVS1"))
    ap.add_argument("--cics-stc", default=os.environ.get("CARDDEMO_CICS_STC", "CICSTS61"))
    ap.add_argument("--cics-load", default=os.environ.get("CICS_LOAD", "CICSTS61.CICS.SDFHLOAD"))
    ap.add_argument("--cics-cob", default=os.environ.get("CICS_COB", "CICSTS61.CICS.SDFHCOB"))
    ap.add_argument("--cics-mac", default=os.environ.get("CICS_MAC", "CICSTS61.CICS.SDFHMAC"))
    ap.add_argument("--cics-samp", default=os.environ.get("CICS_SAMP", "CICSTS61.CICS.SDFHSAMP"))
    ap.add_argument("--cics-csd", default=os.environ.get("CICS_CSD", "CICSTS61.DFHCSD"))
    ap.add_argument("--coblib", default=os.environ.get("COBLIB", "IGY.V6R4M0.SIGYCOMP"))
    ap.add_argument("--ftp-host", default=os.environ.get("OS390_FTP_HOST", "10.1.1.2"))
    ap.add_argument("--ftp-port", type=int, default=int(os.environ.get("OS390_FTP_PORT", "21")))
    ap.add_argument("--ftp-user", default=os.environ.get("OS390_FTP_USER", "ibmuser"))
    ap.add_argument("--ftp-pass", default=os.environ.get("OS390_FTP_PASS", ""))
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("CARDDEMO_TIMEOUT", "900")))
    ap.add_argument("--keep-spool", action="store_true")
    ap.add_argument("--alloc", action="store_true")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--init-vsam", action="store_true")
    ap.add_argument("--csd", action="store_true")
    ap.add_argument("--all-base", action="store_true")
    args = ap.parse_args(argv)
    if args.all_base:
        args.alloc = args.upload = args.compile = args.init_vsam = args.csd = True
    if not any((args.alloc, args.upload, args.compile, args.init_vsam, args.csd)):
        ap.error("choose at least one action, or --all-base")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    cfg = Config(
        repo=repo,
        evidence=(repo / args.evidence).resolve() if not args.evidence.is_absolute() else args.evidence,
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
    write_manifest(cfg, args)
    run_all(cfg, args)
    print(f"done; evidence in {cfg.evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
