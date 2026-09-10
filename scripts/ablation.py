"""Факторный эксперимент и цена подтверждения на фиксированном стресс-наборе."""

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np

from barcode_reader.decoder import decode
from barcode_reader.engineering import load_config
from barcode_reader.metrics import key_record, score, wilson
from barcode_reader.provenance import metadata
from barcode_reader.synthetic import dataset


def run(boxes=60):
    cv2.setNumThreads(1)
    rows = []
    ledger = []
    modes = [
        ("auto_0", None, False, "raw"),
        ("auto_45", None, True, "raw"),
        ("code128_0", "Code128", False, "raw"),
        ("code128_45", "Code128", True, "raw"),
        ("code128_45_clahe", "Code128", True, "clahe"),
        ("code128_45_upscale", "Code128", True, "upscale"),
        ("legacy_enhanced", None, False, "enhanced"),
    ]
    for sample in dataset(boxes=boxes):
        expected = {("Code 128", x.encode().hex()) for x in sample["expected"]}
        for name, formats, diagonal, prep in modes:
            started = time.perf_counter()
            per_frame = []
            for frame in sample["frames"]:
                found = {
                    d.key
                    for d in decode(
                        frame,
                        prep == "enhanced",
                        try_diagonal=diagonal,
                        formats=formats,
                    )
                }
                if prep in ("clahe", "upscale"):
                    extra = (
                        cv2.createCLAHE(2.0, (8, 8)).apply(frame)
                        if prep == "clahe"
                        else cv2.resize(
                            frame, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
                        )
                    )
                    found |= {
                        d.key
                        for d in decode(extra, try_diagonal=diagonal, formats=formats)
                    }
                per_frame.append(found)
            elapsed = (time.perf_counter() - started) * 1000
            union = set.union(*per_frame)
            policies = {
                "one": union,
                "two_frames": {k for k in union if sum(k in f for f in per_frame) >= 2},
                "demo_schema": {
                    k
                    for k in union
                    if re.fullmatch(rb"OZ[0-9]{6}", bytes.fromhex(k[1]))
                },
            }
            for policy, found in policies.items():
                rows.append(
                    {
                        "box_id": sample["box_id"],
                        "level": sample["level"],
                        "mode": name,
                        "policy": policy,
                        **score(expected, found),
                        "latency_ms": elapsed,
                    }
                )
            ledger.append(
                {
                    "box_id": sample["box_id"],
                    "mode": name,
                    "expected": [key_record(k) for k in sorted(expected)],
                    "frames": [[key_record(k) for k in sorted(f)] for f in per_frame],
                }
            )
        print(sample["box_id"], flush=True)
    summary = []
    for name, *_ in modes:
        for policy in policies:
            for level in ("all", "clean", "moderate", "hard"):
                subset = [
                    r
                    for r in rows
                    if r["mode"] == name
                    and r["policy"] == policy
                    and (level == "all" or r["level"] == level)
                ]
                n = len(subset)
                exact = sum(r["exact"] for r in subset)
                tp = sum(r["tp"] for r in subset)
                fn = sum(r["fn"] for r in subset)
                summary.append(
                    {
                        "mode": name,
                        "policy": policy,
                        "level": level,
                        "boxes": n,
                        "exact": exact,
                        "exact_ci95": wilson(exact, n),
                        "tp": tp,
                        "fn": fn,
                        "fp": sum(r["fp"] for r in subset),
                        "recall_ci95": wilson(tp, tp + fn),
                        "p95_ms": float(
                            np.percentile([r["latency_ms"] for r in subset], 95)
                        ),
                    }
                )
    result = {
        "seed": 20260909,
        "metadata": metadata(load_config(), boxes=boxes),
        "cpu": metadata()["cpu"],
        "summary": summary,
        "rows": rows,
        "policy_note": "demo_schema = OZ + 6 цифр: контракт генератора, доступный прикладной фильтр только после согласования формата с WCS. Две строки полос одного скана отдельными кадрами не считаются.",
        "uncertainty": "Wilson 95% для коробок; интервалы полноты по значениям описательные: коды одной коробки зависимы.",
    }
    (ROOT / "results/ablation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    (ROOT / "results/ablation_predictions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ledger)
    )


if __name__ == "__main__":
    run()
