"""Входы отчёта проверяются и фиксируются хешами до построения страниц."""

import hashlib
import json
from pathlib import Path

from .provenance import config_hash, metadata

RESULT_NAMES = (
    "calculations",
    "engineering_review",
    "nominal",
    "load_replay",
    "ablation",
)


def load_materials(root: Path) -> tuple[dict, dict]:
    results = {
        name: json.loads((root / "results" / f"{name}.json").read_text())
        for name in RESULT_NAMES
    }
    expected = config_hash(json.loads((root / "configs/conveyor.json").read_text()))
    for name, result in results.items():
        if result.get("metadata", {}).get("config_sha256") != expected:
            raise ValueError(
                f"{name}: результаты получены с другим или неизвестным конфигом; повторите эксперимент"
            )
    files = [root / "results" / f"{name}.json" for name in RESULT_NAMES]
    files.extend(
        [
            root / "results/nominal_manifest.json",
            root / "results/ablation_predictions.jsonl",
        ]
    )
    manifest = {
        "metadata": metadata(),
        "inputs": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        "runs": {name: r["metadata"]["run_id"] for name, r in results.items()},
        "config_sha256": expected,
    }
    return results, manifest
