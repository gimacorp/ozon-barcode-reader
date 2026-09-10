"""Иллюстрации реальных исходников, ложного чтения и контраста минимального кода."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
import matplotlib

matplotlib.use("Agg")
import cv2
import matplotlib.pyplot as plt
import numpy as np

from barcode_reader.decoder import _views, decode
from barcode_reader.optics import contrast, degrade
from barcode_reader.synthetic import dataset, label


def run():
    dest = ROOT / "docs/figures"
    dest.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 15})
    real = []
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), layout="constrained")
    for ax, name in zip(axes, ["assignment_label", "assignment_box"]):
        frame = cv2.imread(str(ROOT / f"results/source_images/{name}.png"), 0)
        d = decode(
            frame, True, formats="Code128,Code39,EAN13,EAN8,ITF,UPCA,UPCE,Codabar"
        )
        real.append(
            {
                "file": name + ".png",
                "width": frame.shape[1],
                "height": frame.shape[0],
                "diagram_estimate_px_per_mm": 188 / 60
                if name == "assignment_label"
                else None,
                "project_X_033_estimate_px": 188 / 60 * 0.33
                if name == "assignment_label"
                else None,
                "found": [
                    {"format": x.format, "payload_hex": x.payload_hex, "text": x.text}
                    for x in d
                ],
            }
        )
        ax.imshow(frame, cmap="gray")
        ax.set_title(f"{frame.shape[1]} × {frame.shape[0]}: {len(d)} чтений")
        ax.axis("off")
    fig.savefig(dest / "real_sources.png", dpi=180)
    plt.close(fig)
    sample = next(s for s in dataset() if s["box_id"] == "SYN-0023")
    false = None
    for frame_index, frame in enumerate(sample["frames"]):
        for transformed, inv in _views(frame, True, False):
            ds = decode(transformed, try_diagonal=False, formats=None)
            for d in ds:
                if d.text == "O*000904":
                    false = (frame_index, frame, transformed, inv, d)
                    break
            if false:
                break
        if false:
            break
    if false:
        idx, raw, processed, inv, d = false
        poly = np.c_[np.asarray(d.polygon), np.ones(4)] @ inv.T
        x0, y0 = np.maximum(0, np.floor(poly[:, :2].min(0) - 30)).astype(int)
        x1, y1 = np.minimum(
            [raw.shape[1], raw.shape[0]], np.ceil(poly[:, :2].max(0) + 30)
        ).astype(int)
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.1), layout="constrained")
        axes[0].imshow(raw, cmap="gray")
        axes[0].set_title(f"SYN-0023, кадр {idx}")
        axes[0].add_patch(
            plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, color="#005BFF", lw=2)
        )
        axes[1].imshow(raw[y0:y1, x0:x1], cmap="gray")
        axes[1].set_title("Исходный фрагмент")
        p = np.asarray(d.polygon)
        a = np.maximum(0, np.floor(p.min(0) - 30)).astype(int)
        b = np.minimum(
            [processed.shape[1], processed.shape[0]], np.ceil(p.max(0) + 30)
        ).astype(int)
        axes[2].imshow(processed[a[1] : b[1], a[0] : b[0]], cmap="gray")
        axes[2].set_title("Обработка → O*000904\nCode 128")
        for ax in axes:
            ax.axis("off")
        fig.savefig(dest / "false_reading.png", dpi=180)
        plt.close(fig)
    ideal = label("MIN00001", 3.73)
    degraded = degrade(ideal, 0.0032, 11, 2, 0.5)
    decoded = decode(degraded)
    fig, axes = plt.subplots(2, 1, figsize=(10, 4.5), layout="constrained")
    for ax, im, title in zip(
        axes,
        [ideal, degraded],
        [
            "Идеальный код: 3,73 пикселя/модуль",
            "F/11 · дефокус 2 px · смаз 0,5 px · апертура пикселя",
        ],
    ):
        ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(title)
        ax.axis("off")
    fig.savefig(dest / "optical_code.png", dpi=180)
    plt.close(fig)
    (ROOT / "results/visual_evidence.json").write_text(
        json.dumps(
            {
                "real": real,
                "false_read": {
                    "found": bool(false),
                    "expected": sample["expected"],
                    "decoded": "O*000904",
                    "format": "Code 128",
                },
                "optical": {
                    "expected": "MIN00001",
                    "found": [x.text for x in decoded],
                    **contrast(),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    run()
