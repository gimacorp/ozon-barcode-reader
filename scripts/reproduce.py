"""Последовательный полный запуск; общая метка связывает результаты одной серии."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    environment = os.environ | {"OZON_RUN_ID": datetime.now(timezone.utc).isoformat()}
    commands = [
        ["-m", "barcode_reader", "calculate"],
        ["scripts/engineering_review.py"],
        ["scripts/nominal_experiment.py"],
        ["scripts/ablation.py"],
        ["scripts/load_replay.py", "--boxes", "12", "--runs", "3"],
        ["scripts/visual_evidence.py"],
        ["-m", "barcode_reader", "benchmark", "--boxes", "60"],
        ["-m", "barcode_reader.replay"],
        ["scripts/build_report.py"],
        ["scripts/update_readme.py"],
        ["scripts/verify_submission.py"],
    ]
    for command in commands:
        print("Запуск:", " ".join(command), flush=True)
        subprocess.run(
            [sys.executable, *command], cwd=ROOT, env=environment, check=True
        )


if __name__ == "__main__":
    run()
