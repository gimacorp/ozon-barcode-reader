"""Идентификаторы запуска reader и системной монотонной шкалы."""

import hashlib
import platform
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_FALLBACK_DOMAIN = "process-" + uuid.uuid4().hex


def system_clock_domain() -> str:
    """Boot ID ОС; при недоступности изолируем шкалу текущим процессом."""
    path = Path("/proc/sys/kernel/random/boot_id")
    if path.exists():
        return "linux-" + path.read_text().strip()
    if platform.system() == "Darwin":
        try:
            value = subprocess.check_output(
                ["sysctl", "-n", "kern.boottime"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).strip()
            return "darwin-" + hashlib.sha256(value.encode()).hexdigest()[:24]
        except (OSError, subprocess.SubprocessError):
            pass
    return _FALLBACK_DOMAIN


@dataclass(frozen=True)
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    clock_domain: str = field(default_factory=system_clock_domain)
