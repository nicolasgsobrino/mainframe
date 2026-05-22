"""CICS/TN3270 golden-master capture flows."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1:2123")
    parser.add_argument("--applid", default="CICSTS61")
    parser.add_argument("--cics-user", default="IBMUSER")
    parser.add_argument("--cics-password", default=os.environ.get("CICS_PASSWORD", ""))
    parser.add_argument("--outdir", type=Path, default=Path("evidence/carddemo-golden/cics"))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--settle", type=int, default=6)


def new_emulator(timeout: int) -> Any:
    from py3270 import Emulator

    return Emulator(visible=False, timeout=timeout)


def xcmd(em: Any, command: str) -> None:
    em.exec_command(command.encode("ascii"))


def wait_input(em: Any, seconds: int = 4) -> None:
    # ADCD's VTAM/CICS screens are sometimes unlocked before x3270 reports an
    # InputField, so a short fixed wait is more reliable for this environment.
    em.exec_command(f"Wait({seconds},seconds)".encode("ascii"))


def screen_text(em: Any) -> str:
    cmd = em.exec_command(b"Ascii()")
    return "\n".join(line.decode("ascii", errors="replace").rstrip() for line in cmd.data) + "\n"


def capture(em: Any, outdir: Path, name: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{name}.txt").write_text(screen_text(em), encoding="utf-8")
    em.save_screen(str(outdir / f"{name}.html"))


def connect_cics(em: Any, args: argparse.Namespace) -> None:
    em.connect(args.host)
    wait_input(em, args.settle)
    em.send_string(args.applid)
    em.send_enter()
    wait_input(em, args.settle)
    em.send_string(args.cics_user)
    xcmd(em, "Tab")
    xcmd(em, "Tab")
    em.send_string(args.cics_password)
    em.send_enter()
    wait_input(em, args.settle)
    xcmd(em, "Clear")
    wait_input(em, 2)


def start_carddemo(em: Any, outdir: Path, capture_name: str | None = None) -> None:
    em.send_string("CC00")
    em.send_enter()
    wait_input(em)
    if capture_name:
        capture(em, outdir, capture_name)


def login_carddemo(em: Any, user: str, password: str) -> None:
    # Both CardDemo fields are eight characters; the terminal auto-tabs after
    # the full userid, so send password immediately without an extra Tab.
    em.send_string(user)
    em.send_string(password)
    em.send_enter()
    wait_input(em)


def run_admin_user_list(args: argparse.Namespace, outdir: Path) -> None:
    em = new_emulator(args.timeout)
    try:
        connect_cics(em, args)
        start_carddemo(em, outdir, "cics_001_cc00_signon")
        login_carddemo(em, "ADMIN001", "PASSWORD")
        capture(em, outdir, "cics_002_admin_menu")
        em.send_string("01")
        em.send_enter()
        wait_input(em)
        capture(em, outdir, "cics_003_admin_user_list")
    finally:
        em.terminate()


def run_user_account_view(args: argparse.Namespace, outdir: Path) -> None:
    em = new_emulator(args.timeout)
    try:
        connect_cics(em, args)
        start_carddemo(em, outdir)
        login_carddemo(em, "USER0001", "PASSWORD")
        capture(em, outdir, "cics_010_user_menu")
        em.send_string("01")
        em.send_enter()
        wait_input(em)
        capture(em, outdir, "cics_011_account_view_blank")
        em.send_string("00000000001")
        em.send_enter()
        wait_input(em)
        capture(em, outdir, "cics_012_account_view_00000000001")
    finally:
        em.terminate()


def run_user_card_list(args: argparse.Namespace, outdir: Path) -> None:
    em = new_emulator(args.timeout)
    try:
        connect_cics(em, args)
        start_carddemo(em, outdir)
        login_carddemo(em, "USER0001", "PASSWORD")
        em.send_string("03")
        em.send_enter()
        wait_input(em)
        capture(em, outdir, "cics_020_card_list")
    finally:
        em.terminate()


def run_from_args(args: argparse.Namespace) -> int:
    outdir = args.outdir.resolve()
    run_admin_user_list(args, outdir)
    run_user_account_view(args, outdir)
    run_user_card_list(args, outdir)
    print(f"captured CICS golden screens in {outdir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    return parser.parse_args()


def main() -> int:
    return run_from_args(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
