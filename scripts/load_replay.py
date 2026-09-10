"""Повторные CPU-прогоны проектных растров через ограниченную очередь EDF."""

import argparse
import heapq
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from PIL import Image

from barcode_reader.decoder import decode
from barcode_reader.engineering import load_config
from barcode_reader.provenance import metadata
from barcode_reader.scheduling import arrivals, simulate
from barcode_reader.synthetic import label

CONFIG = {}


def init_worker(config: dict) -> None:
    global CONFIG
    CONFIG = config
    cv2.setNumThreads(1)
    decode(np.full((100, 100), 255, np.uint8))


def work(job, seed: int) -> dict:
    start = time.monotonic()
    c = CONFIG
    area = job.kind == "area"
    h = c["area_pixels_y"] if area else job.rows[1] - job.rows[0]
    w = c["area_pixels_x"] if area else c["line_pixels"]
    total = int(np.ceil(c["box_length_mm"] * c["line_rate_hz"] / c["speed_mm_s"]))
    image = np.full((h, w), 255, np.uint8)
    profile = ("clean", "difficult", "partial_blackout")[job.box % 3]
    blackout = profile == "partial_blackout" and area and job.sequence == 1
    truth = {f"L{job.channel[0:2]}{i:02}" for i in range(c["max_labels_per_face"])}
    visible = set()
    if not blackout:
        for index, text in enumerate(sorted(truth)):
            angle = [0, 45, 90, 135][(index + job.box + seed) % 4]
            stamp = np.array(
                Image.fromarray(
                    label(
                        text,
                        c["min_module_mm"]
                        * w
                        / (
                            c["area_fov_width_mm"]
                            if area
                            else c["line_fov_horizontal_mm"]
                        ),
                    )
                ).rotate(
                    angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=255
                )
            )
            if profile == "difficult":
                stamp = cv2.GaussianBlur(stamp, (5, 5), 1.1)
                stamp = np.uint8(128 + (stamp.astype(float) - 128) * 0.45)
            sh, sw = stamp.shape
            x = int(w * (0.25 + 0.5 * (index % 2))) - sw // 2
            global_y = int(
                (h * (0.25 + 0.5 * (index // 2)))
                if area
                else total * (index + 1) / (c["max_labels_per_face"] + 1)
            )
            y = global_y - sh // 2 - (0 if area else job.rows[0])
            a, b = max(0, y), min(h, y + sh)
            if b > a:
                image[a:b, x : x + sw] = stamp[a - y : b - y]
            if y >= 0 and y + sh <= h:
                visible.add(text)
    prepared = time.monotonic()
    detections = decode(image)
    end = time.monotonic()
    found = {d.text for d in detections}
    return {
        "kind": job.kind,
        "channel": job.channel,
        "profile": profile,
        "start": start,
        "end": end,
        "service_s": end - start,
        "decode_s": end - prepared,
        "prepare_s": prepared - start,
        "expected_visible": sorted(visible),
        "found": sorted(found),
        "correct": visible <= found and found <= truth,
        "blank": not visible,
        "truth": sorted(truth),
    }


def trial(c: dict, boxes: int, workers: int, seed: int) -> dict:
    jobs = arrivals(boxes, config=c)
    measurements, queued, running, cancelled = [], [], {}, set()
    maxq = peak = index = 0
    with ProcessPoolExecutor(
        max_workers=workers, initializer=init_worker, initargs=(c,)
    ) as pool:
        list(pool.map(work, [jobs[0]] * (workers * 2), [seed] * (workers * 2)))
        start = time.monotonic()
        while index < len(jobs) or queued or running:
            now = time.monotonic() - start
            for future, job in list(running.items()):
                if future.done():
                    result = future.result()
                    measurements.append(
                        result
                        | {
                            "box": job.box,
                            "arrival": job.arrival,
                            "deadline": job.deadline,
                            "sequence": job.sequence,
                        }
                    )
                    del running[future]
            while index < len(jobs) and jobs[index].arrival <= now:
                job = jobs[index]
                index += 1
                if len(queued) >= c["processing_queue_capacity"]:
                    cancelled.add(job.box)
                else:
                    heapq.heappush(queued, (job.deadline, index, job))
            while queued and len(running) < workers:
                _, _, job = heapq.heappop(queued)
                if job.box in cancelled or now + c["delivery_budget_s"] > job.deadline:
                    cancelled.add(job.box)
                    continue
                running[pool.submit(work, job, seed)] = job
            maxq = max(maxq, len(queued))
            peak = max(peak, len(queued) + len(running))
            if index < len(jobs) or running:
                time.sleep(0.001)
    outcomes = []
    for box in range(boxes):
        rows = [r for r in measurements if r["box"] == box]
        scheduled = [j for j in jobs if j.box == box]
        ack = (
            max((r["end"] for r in rows), default=start)
            - start
            + c["delivery_budget_s"]
        )
        expected = {
            f"L{face[:2]}{i:02}"
            for face in ("top", "bottom", "left", "right", "front", "rear")
            for i in range(c["max_labels_per_face"])
        }
        found = {text for r in rows for text in r["found"]}
        outcomes.append(
            {
                "box": box,
                "finish_after_last_exposure_ms": (
                    ack - max(j.captured_s for j in scheduled)
                )
                * 1000,
                "ack_s": ack,
                "late": ack > scheduled[0].deadline
                or box in cancelled
                or len(rows) != len(scheduled),
                "jobs": len(rows),
                "expected_values": len(expected),
                "found_values": len(found),
                "exact_set": expected == found,
            }
        )
    lat = [r["finish_after_last_exposure_ms"] for r in outcomes]
    return {
        "seed": seed,
        "boxes": boxes,
        "p95_ms": float(np.percentile(lat, 95)),
        "p99_ms": float(np.percentile(lat, 99)),
        "late_fraction": sum(r["late"] for r in outcomes) / boxes,
        "max_queue": maxq,
        "peak_inflight_including_running": peak,
        "outcomes": outcomes,
        "measurements": [
            r | {"start": r["start"] - start, "end": r["end"] - start}
            for r in measurements
        ],
    }


def run(
    boxes: int = 12,
    workers: int | None = None,
    runs: int = 3,
    config_path: str = "configs/conveyor.json",
) -> dict:
    c = load_config(config_path)
    workers = workers or c["processing_workers"]
    trials = []
    for i in range(runs):
        result = trial(c, boxes, workers, 20260910 + i)
        trials.append(result)
        print(
            f"Прогон {i + 1}/{runs}: p95={result['p95_ms']:.1f} мс; просрочки={result['late_fraction']:.1%}",
            flush=True,
        )
    measurements = [
        r | {"run": i} for i, t in enumerate(trials) for r in t["measurements"]
    ]
    outcomes = [r | {"run": i} for i, t in enumerate(trials) for r in t["outcomes"]]
    service = {
        kind: [r["service_s"] for r in measurements if r["kind"] == kind]
        for kind in ("area", "line")
    }
    model_jobs = arrivals(1000, config=c)
    last = {j.box: j.captured_s for j in sorted(model_jobs, key=lambda j: j.captured_s)}
    models = []
    for count in (1, 4, 8):
        for multiplier in (1.0, 1.5, 2.0):
            sim = simulate(
                model_jobs,
                lambda j: float(np.percentile(service[j.kind], 95)) * multiplier,
                count,
                c["processing_queue_capacity"],
                delivery_s=c["delivery_budget_s"],
            )
            lat = [
                (o["ack_s"] - last[o["box"]]) * 1000
                for o in sim["outcomes"]
                if not o["late"]
            ]
            models.append(
                {
                    "workers": count,
                    "service_multiplier": multiplier,
                    "boxes": 1000,
                    "late_fraction": sum(x["late"] for x in sim["outcomes"]) / 1000,
                    "max_queue": sim["max_queue"],
                    "p95_success_ms": float(np.percentile(lat, 95)) if lat else None,
                }
            )
    latency = [r["finish_after_last_exposure_ms"] for r in outcomes]
    result = {
        "metadata": metadata(c, boxes_per_run=boxes, runs=runs, workers=workers),
        "workers": workers,
        "boxes": len(outcomes),
        "runs": runs,
        "interval_s": c["leading_edge_interval_s"],
        "capacity": c["processing_queue_capacity"],
        "peak_inflight_including_running": max(
            t["peak_inflight_including_running"] for t in trials
        ),
        "max_queue": max(t["max_queue"] for t in trials),
        "p95_ms": float(np.percentile(latency, 95)),
        "p99_ms": float(np.percentile(latency, 99)),
        "late_fraction": sum(r["late"] for r in outcomes) / len(outcomes),
        "all_decodes_correct": all(r["correct"] for r in measurements),
        "exact_boxes": sum(r["exact_set"] for r in outcomes),
        "blank_images": sum(r["blank"] for r in measurements),
        "service_p50_ms": {
            k: float(np.percentile(v, 50)) * 1000 for k, v in service.items()
        },
        "service_p95_ms": {
            k: float(np.percentile(v, 95)) * 1000 for k, v in service.items()
        },
        "outcomes": outcomes,
        "trials": [
            {k: v for k, v in t.items() if k not in ("outcomes", "measurements")}
            for t in trials
        ],
        "models": models,
        "measurements": measurements,
        "scope": "Новые проектные массивы создаются внутри каждого задания; время выделения/подготовки включено в service. До 24 постоянных значений на коробку, 4 на грань; 0/45/90/135°, слабый контраст, размытие и пустые наблюдения. Растры полос получены из согласованных координат четырёх этикеток полного скана. EDF ограничивает очередь и отменяет просроченный остаток коробки. Передача данных IPC, SDK и DMA моделируется временем готовности; изображения создаются в рабочих процессах. Три независимых запуска пула описывают вариацию на одной машине; p99 малой выборки описательный.",
    }
    result["cpu"] = result["metadata"]["cpu"]
    (ROOT / "results/load_replay.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--boxes", type=int, default=12)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--config", default="configs/conveyor.json")
    a = p.parse_args()
    run(a.boxes, runs=a.runs, config_path=a.config)
