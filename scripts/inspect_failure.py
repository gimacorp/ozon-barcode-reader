"""Воспроизведение одной синтетической коробки, включая трудный пример SYN-0023."""

import argparse
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from barcode_reader.decoder import decode
from barcode_reader.synthetic import dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--box-id", default="SYN-0023")
    parser.add_argument("--output", default="output/failure")
    args = parser.parse_args()
    try:
        index = int(args.box_id.removeprefix("SYN-"))
    except ValueError:
        parser.error("Формат идентификатора: SYN-0023")
    if not 0 <= index < 10000:
        parser.error("Индекс должен быть от 0 до 9999")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sample = next(s for i, s in enumerate(dataset(boxes=index + 1)) if i == index)
    result = {"box_id": sample["box_id"], "expected": sample["expected"], "frames": []}
    for i, frame in enumerate(sample["frames"]):
        cv2.imwrite(str(out / f"frame_{i}.png"), frame)
        result["frames"].append(
            {
                "frame": i,
                "base": [
                    d.text for d in decode(frame, try_diagonal=False, formats=None)
                ],
                "enhanced": [
                    d.text
                    for d in decode(frame, True, try_diagonal=False, formats=None)
                ],
                "current": [d.text for d in decode(frame)],
            }
        )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    (out / "result.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
