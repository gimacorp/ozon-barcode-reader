"""Измерение чтения синтетических кадров проектного размера на текущем CPU."""

import json
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from barcode_reader.decoder import decode
from barcode_reader.synthetic import label


def main():
    cv2.setNumThreads(1)
    records = []
    for name, h, w in [("area", 7000, 9344), ("line_strip", 2048, 8192)]:
        frame = np.full((h, w), 178, np.uint8)
        expected = set()
        for i, (x, y) in enumerate(
            [(w // 4, h // 3), (w // 2, h // 2), (3 * w // 4, 2 * h // 3)]
        ):
            text = f"NATIVE{i:04d}"
            expected.add(text)
            stamp = label(text, 3.86)
            sh, sw = stamp.shape
            frame[y : y + sh, x : x + sw] = stamp
        started = time.perf_counter()
        found = {d.text for d in decode(frame)}
        records.append(
            {
                "kind": name,
                "width": w,
                "height": h,
                "milliseconds": (time.perf_counter() - started) * 1000,
                "expected": sorted(expected),
                "found": sorted(found),
                "exact_set": found == expected,
            }
        )
    out = ROOT / "results/native_resolution.json"
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "opencv_threads": 1,
        "measurements": records,
        "limitation": "По одному чистому синтетическому изображению каждого размера на текущем CPU. Это проверка размера и единичной задержки; p95/p99 и промышленная нагрузка требуют отдельного стенда.",
    }
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
