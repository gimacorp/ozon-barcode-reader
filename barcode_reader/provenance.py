"""Автоматические сведения о машине, исходниках и параметрах запуска."""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=3
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def config_hash(config: dict) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def cpu_model() -> str:
    explicit = os.environ.get("OZON_CPU_MODEL")
    if explicit:
        return explicit
    if platform.system() == "Darwin":
        return command(["sysctl", "-n", "machdep.cpu.brand_string"]) or "unavailable"
    path = Path("/proc/cpuinfo")
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return "unavailable"


def metadata(config: dict | None = None, **parameters) -> dict:
    packages = {}
    for name in (
        "numpy",
        "opencv-python-headless",
        "zxing-cpp",
        "python-barcode",
        "Pillow",
        "reportlab",
        "pytest",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    sources = sorted(
        [
            *ROOT.glob("barcode_reader/*.py"),
            *ROOT.glob("scripts/*.py"),
            *ROOT.glob("configs/*.json"),
        ]
    )
    sha = hashlib.sha256()
    for path in sources:
        sha.update(str(path.relative_to(ROOT)).encode())
        sha.update(path.read_bytes())
    return {
        "run_id": os.environ.get("OZON_RUN_ID", datetime.now(timezone.utc).isoformat()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cpu": cpu_model(),
        "cpu_source": "OZON_CPU_MODEL" if os.environ.get("OZON_CPU_MODEL") else "OS",
        "os": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version.split()[0],
        "packages": packages,
        "git_revision": command(["git", "rev-parse", "HEAD"]),
        "git_description": command(["git", "describe", "--tags", "--always"]),
        "git_dirty": bool(command(["git", "status", "--porcelain"])),
        "source_sha256": sha.hexdigest(),
        "config_sha256": config_hash(config) if config else None,
        "config": config,
        "parameters": parameters,
    }
