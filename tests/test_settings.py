from __future__ import annotations

import os
import subprocess
import sys


def test_secret_key_required_when_debug_disabled():
    env = os.environ.copy()
    env.pop("DJANGO_SECRET_KEY", None)
    env["DJANGO_DEBUG"] = "0"

    result = subprocess.run(
        [sys.executable, "-c", "import carddemo.settings"],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_debug_mode_allows_development_secret_fallback():
    env = os.environ.copy()
    env.pop("DJANGO_SECRET_KEY", None)
    env["DJANGO_DEBUG"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", "import carddemo.settings"],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
