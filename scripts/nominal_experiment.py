"""Постоянные этикетки, движение коробки, проектная проекция и оптические искажения."""

import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from barcode import Code128

from barcode_reader.decoder import decode, decode_strips
from barcode_reader.engineering import load_config, working_distance
from barcode_reader.geometry import project
from barcode_reader.metrics import key_record, score, wilson
from barcode_reader.optics import defocus_diameter, degrade
from barcode_reader.provenance import metadata


def stamp(text, c):
    img = np.full(
        (round(c["max_label_height_mm"] * 10), round(c["max_label_width_mm"] * 10)),
        255,
        np.uint8,
    )
    for i, b in enumerate(Code128(text).build()[0]):
        if b == "1":
            img[
                45:205,
                round((12 + i) * c["min_module_mm"] * 10) : round(
                    (13 + i) * c["min_module_mm"] * 10
                ),
            ] = 0
    return img


def patch(text, angle, center, c):
    a = np.radians(angle)
    r = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return (
        np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])
        * [c["max_label_width_mm"], c["max_label_height_mm"]]
    ) @ r.T + center


def paste(canvas, img, uv, pixel, ap, coc, motion=0.5):
    margin = 32
    lo = np.floor(uv.min(0)).astype(int) - margin
    hi = np.ceil(uv.max(0)).astype(int) + margin
    w, h = hi - lo
    src = np.float32(
        [
            [0, 0],
            [img.shape[1] - 1, 0],
            [img.shape[1] - 1, img.shape[0] - 1],
            [0, img.shape[0] - 1],
        ]
    )
    roi = cv2.warpPerspective(
        img,
        cv2.getPerspectiveTransform(src, (uv - lo).astype(np.float32)),
        (w, h),
        borderValue=255,
    )
    roi = degrade(roi, pixel, ap, coc, motion)
    x, y = lo
    hh, ww = canvas.shape
    if x < 0 or y < 0 or x + w > ww or y + h > hh:
        raise ValueError("Этикетка за полем зрения")
    canvas[y : y + h, x : x + w] = np.minimum(canvas[y : y + h, x : x + w], roi)


def run(boxes=12, config_path="configs/conveyor.json"):
    c = load_config(config_path)
    cv2.setNumThreads(1)
    f = c["area_focal_length_mm"]
    pixel = c["area_sensor_pixel_um"] / 1000
    ap = c["area_aperture"]
    wd = working_distance(f, c["area_pixels_x"] * pixel, c["area_fov_width_mm"])
    dx = math.sqrt(wd**2 - c["area_elevation_mm"] ** 2)
    middle = c["box_height_mm"] / 2
    pos = np.array([-dx, 0.0, middle + c["area_elevation_mm"]])
    target = np.array([0.0, 0.0, middle])
    fp = f * wd / (wd - f) / pixel
    step = c["speed_mm_s"] / c["area_frame_rate_hz"]
    total = math.ceil(c["box_length_mm"] * c["line_rate_hz"] / c["speed_mm_s"])
    rows = []
    manifest = []
    start = time.perf_counter()
    dest = ROOT / "docs/figures"
    dest.mkdir(exist_ok=True)
    for box in range(boxes):
        expected = set()
        found = set()
        perface = []
        phase = np.linspace(-step / 2, step / 2, boxes)[box]
        for face_idx, face in enumerate(
            ["top", "bottom", "left", "right", "front", "rear"]
        ):
            labels = []
            centers = (
                [
                    (x * c["box_width_mm"], y * c["box_height_mm"])
                    for y in (0.25, 0.75)
                    for x in (-0.25, 0.25)
                ]
                if face in ("front", "rear")
                else [
                    (
                        x
                        * (
                            c["box_height_mm"]
                            if face in ("left", "right")
                            else c["box_width_mm"]
                        ),
                        y * c["box_length_mm"],
                    )
                    for y in (0.25, 0.75)
                    for x in (0.25, 0.75)
                ]
            )
            for i, center in enumerate(centers[: c["max_labels_per_face"]]):
                text = f"N{box:02d}{face_idx}{i}"
                key = ("Code 128", text.encode().hex())
                expected.add(key)
                angle = (box * 15 + i * 45) % 180
                labels.append((text, stamp(text, c), patch(text, angle, center, c)))
            fs = set()
            frames = []
            shifts = (
                (
                    np.arange(c["area_frames_per_box"])
                    - (c["area_frames_per_box"] - 1) / 2
                )
                * step
                + phase
                if face in ("front", "rear")
                else [0]
            )
            for frame_index, shift in enumerate(shifts):
                area = face in ("front", "rear")
                canvas = np.full(
                    (c["area_pixels_y"], c["area_pixels_x"])
                    if area
                    else (total, c["line_pixels"]),
                    255,
                    np.uint8,
                )
                details = []
                for text, img, corners in labels:
                    if area:
                        pts = np.c_[np.full(4, shift), corners]
                        uv, depth = project(
                            pts, pos, target, fp, c["area_pixels_x"], c["area_pixels_y"]
                        )
                        coc = float(max(defocus_diameter(f, ap, wd, depth, pixel)))
                        paste(
                            canvas,
                            img,
                            uv,
                            pixel,
                            ap,
                            coc,
                            c["speed_mm_s"]
                            * c["area_exposure_us"]
                            * 1e-6
                            * c["area_pixels_x"]
                            / c["area_fov_width_mm"],
                        )
                    else:
                        fov = (
                            c["line_fov_vertical_mm"]
                            if face in ("left", "right")
                            else c["line_fov_horizontal_mm"]
                        )
                        lp = c["line_sensor_pixel_um"] / 1000
                        lf = c["line_focal_length_mm"]
                        la = c["line_aperture"]
                        focus = working_distance(lf, c["line_pixels"] * lp, fov)
                        # Пограничный допуск: смещение + размер + yaw + roll + изгиб.
                        base = (
                            3 + 2 + 1.745 + 1
                            if fov == 450
                            else (5 + 2 + 1 if face == "top" else -2)
                        )
                        depth = (
                            focus
                            + base
                            + (corners[:, 1] - c["box_length_mm"] / 2)
                            * math.sin(math.radians(0.5))
                        )
                        uv = np.c_[
                            c["line_pixels"] / 2
                            + (
                                corners[:, 0]
                                - (
                                    c["box_height_mm"]
                                    if face in ("left", "right")
                                    else c["box_width_mm"]
                                )
                                / 2
                            )
                            * (c["line_pixels"] / fov)
                            * focus
                            / depth,
                            corners[:, 1] * c["line_rate_hz"] / c["speed_mm_s"],
                        ]
                        coc = float(max(defocus_diameter(lf, la, focus, depth, lp)))
                        paste(
                            canvas,
                            img,
                            uv,
                            lp,
                            la,
                            coc,
                            c["line_exposure_us"] * 1e-6 * c["line_rate_hz"],
                        )
                    details.append(
                        {
                            "text": text,
                            "physical_corners_mm": corners.tolist(),
                            "image_corners_px": uv.tolist(),
                            "coc_px": coc,
                        }
                    )
                readings = (
                    decode(canvas)
                    if area
                    else decode_strips(
                        canvas,
                        rows=c["line_strip_rows"],
                        overlap=c["line_strip_overlap_rows"],
                    )
                )
                unexpected = [d for d in readings if d.key not in expected]
                if unexpected:
                    failure_dir = ROOT / "results/nominal_failures"
                    failure_dir.mkdir(exist_ok=True)
                    for index, d in enumerate(unexpected):
                        polygon = np.asarray(d.polygon)
                        lo = np.maximum(0, np.floor(polygon.min(0) - 50)).astype(int)
                        hi = np.minimum(
                            [canvas.shape[1], canvas.shape[0]],
                            np.ceil(polygon.max(0) + 50),
                        ).astype(int)
                        cv2.imwrite(
                            str(
                                failure_dir / f"{box}-{face}-{frame_index}-{index}.png"
                            ),
                            canvas[lo[1] : hi[1], lo[0] : hi[0]],
                        )
                fs |= {d.key for d in readings}
                frames.append(
                    {
                        "frame": frame_index,
                        "shift_mm": float(shift),
                        "detections": [key_record(d.key) for d in readings],
                        "labels": details,
                    }
                )
                if box == 0 and face == "rear" and frame_index == 2:
                    # Полный кадр сохраняется без изменения разрешения; рамки в отдельном превью.
                    cv2.imwrite(str(ROOT / "results/nominal_frame.png"), canvas)
                    view = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
                    for d in readings:
                        p = np.int32(d.polygon)
                        cv2.polylines(view, [p], True, (255, 90, 0), 12)
                        cv2.putText(
                            view,
                            d.text,
                            tuple(p[0]),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            3,
                            (255, 90, 0),
                            6,
                        )
                    cv2.imwrite(
                        str(dest / "nominal_reading.png"),
                        cv2.resize(view, (1402, 1050)),
                    )
            found |= fs
            perface.append({"face": face, "found": len(fs), "expected": len(labels)})
            manifest.append(
                {"box": box, "face": face, "phase_mm": float(phase), "frames": frames}
            )
        rows.append({"box": box, **score(expected, found), "faces": perface})
        print(
            f"Номинальная коробка {box + 1}/{boxes}: {len(found)}/{len(expected)}",
            flush=True,
        )
    exact = sum(r["exact"] for r in rows)
    tp = sum(r["tp"] for r in rows)
    result = {
        "seed": 20260909,
        "boxes": boxes,
        "metadata": metadata(c, boxes=boxes, seed=20260909),
        "labels": sum(r["expected"] for r in rows),
        "unique_values_found": tp,
        "exact_boxes": exact,
        "exact_ci95": wilson(exact, boxes),
        "rows": rows,
        "elapsed_s": time.perf_counter() - start,
        "model": "Постоянные этикетки, до 4 на каждой из 6 граней. Размеры растров, сетка кадров, масштаб, скорость, выдержка и полосы взяты из сохранённого конфига. Проекция тонкой линзы, дефокус по худшему углу этикетки, дифракция, апертура пикселя и условная аберрация sigma=0.35 px.",
        "limitations": "Плоские матовые этикетки, постоянное освещение, без шума фотонов, бликов, окклюзий и калибровочных ошибок. Проекции торцов симметричны. Скорость/позиции заданы моделью; это проверка согласованности проекта.",
    }
    (ROOT / "results/nominal.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    (ROOT / "results/nominal_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    from scripts.presentation_evidence import run as present

    present()


if __name__ == "__main__":
    run()
