"""Small z/OS FTP/JES helpers used by capture-golden workflows."""
from __future__ import annotations

import io
import re
import ssl
import time
from dataclasses import dataclass
from ftplib import FTP_TLS
from pathlib import Path


@dataclass
class ZosConfig:
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


def connect(cfg: ZosConfig, jes: bool = False) -> FTP_TLS:
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


def list_jobs(cfg: ZosConfig) -> dict[str, str]:
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


def submit_job(cfg: ZosConfig, name: str, jcl: str, ok_rc: int = 4) -> tuple[str, int, Path]:
    payload = "\n".join(line.rstrip() for line in jcl.splitlines()).rstrip() + "\n"
    ftp = connect(cfg, jes=True)
    try:
        resp = ftp.storlines("STOR SUBMIT", io.BytesIO(payload.encode("ascii", errors="replace")))
    finally:
        ftp.quit()
    match = re.search(r"JOB\d+", resp)
    if not match:
        raise RuntimeError(f"{name}: unexpected JES submit response: {resp!r}")
    job_id = match.group(0)
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


def normalize_fb80(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.expandtabs(8).rstrip("\r\n")
        if len(line) > 80:
            line = line[:80]
        out.append(line)
    return out


def prepare_text_ftp(ftp: FTP_TLS) -> None:
    ftp.voidcmd("TYPE A")
    for cmd in ("SITE SBDATACONN=(IBM-1047,ISO8859-1)", "SITE RECFM=FB LRECL=80 BLKSIZE=0"):
        try:
            ftp.sendcmd(cmd)
        except Exception:
            pass


def mvs_text(cfg: ZosConfig, dsn: str, text: str) -> None:
    ftp = connect(cfg)
    try:
        prepare_text_ftp(ftp)
        lines = normalize_fb80(text)
        data = ("\n".join(lines) + "\n").encode("latin-1", errors="replace")
        ftp.storlines(f"STOR '{dsn}'", io.BytesIO(data))
    finally:
        ftp.quit()
