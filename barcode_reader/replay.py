"""Короткий сквозной replay с изображениями и производственным контрактом захвата."""

import json
import math
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from .assignment import FaceRegion
from .control import BoxTracker
from .coverage import CaptureContract
from .engineering import load_config
from .pipeline import Capture, Pipeline
from .provenance import metadata
from .scheduling import arrivals, simulate
from .session import Session
from .synthetic import label
from .transport import DurableWCS, Outbox


def run_replay(
    *, missing_strip: bool = False, directory: str | Path | None = None
) -> dict:
    c = load_config("configs/conveyor.json")
    # Уменьшенный растр для CI. Сетка кадров и контракт используют тот же конфиг.
    c.update(line_rate_hz=2000, line_strip_rows=800, line_strip_overlap_rows=400)
    session = Session("integration-session", "integration-os-epoch")
    tracker = BoxTracker(session)
    pipe = Pipeline(tracker)
    jobs = arrivals(1, config=c)
    scheduled = sorted(
        [
            replace(job, box=owner)
            for job in jobs
            for owner in ((0,) if job.kind == "area" else (0, 1))
        ],
        key=lambda job: job.arrival,
    )
    dispatch = simulate(
        scheduled, lambda _: 0.01, workers=2, delivery_s=c["delivery_budget_s"]
    )
    completed = {
        (r["box"], r["channel"], r["sequence"]): r["completed_s"]
        for r in dispatch["completions"]
    }
    end = max(j.captured_s for j in jobs)
    complete_s = max(completed.values()) + 0.01
    area_frames = {
        face: {f"shared-{face}-{i}" for i in range(c["area_frames_per_box"])}
        for face in ("front", "rear")
    }
    total = math.ceil(c["box_length_mm"] * c["line_rate_hz"] / c["speed_mm_s"])
    for name in ("A", "B"):
        contract = CaptureContract.production(
            name,
            total,
            session_id=session.session_id,
            frame_count=c["area_frames_per_box"],
            strip_rows=c["line_strip_rows"],
            overlap=c["line_strip_overlap_rows"],
            area_frames=area_frames,
        )
        tracker.register(name, 0, end, jobs[0].deadline, contract=contract)
    stamp = label("SHARED01", 3.0)
    h, w = stamp.shape
    events = []
    for job in jobs:
        names = ("AB",) if job.kind == "area" else ("A", "B")
        for name in names:
            if (
                missing_strip
                and name == "B"
                and job.channel == "top"
                and job.sequence == 0
            ):
                continue
            height = 800 if job.rows is None else job.rows[1] - job.rows[0]
            frame = np.full((height, 1800 if name == "AB" else 900), 255, np.uint8)
            owners = ["A", "B"] if name == "AB" else [name]
            regions = []
            for index, owner in enumerate(owners):
                x = 900 * index + 450 - w // 2
                frame[100 : 100 + h, x : x + w] = stamp
                regions.append(
                    FaceRegion(
                        owner, job.channel, (900 * index, 0, 900 * (index + 1), height)
                    )
                )
            acquisition = (
                f"shared-{job.channel}-{job.sequence}"
                if name == "AB"
                else f"{name}-{job.channel}-scan"
            )
            capture = Capture(
                frame,
                session.session_id,
                job.channel,
                acquisition,
                regions,
                np.eye(3),
                job.captured_s,
                completed[(0 if name in ("A", "AB") else 1, job.channel, job.sequence)],
                job.rows,
            )
            events.append(pipe.process(capture))
    stale = pipe.process(replace(capture, session_id="previous-session"))
    temp = tempfile.TemporaryDirectory() if directory is None else None
    root = Path(temp.name if temp else directory)
    root.mkdir(parents=True, exist_ok=True)
    out = Outbox(root / "out.db", clock_domain=session.clock_domain)
    wcs = DurableWCS(root / "wcs.db", clock_domain=session.clock_domain)
    results, commands = [], []
    for name in ("A", "B"):
        message = tracker.finalize(name, complete_s)
        out.put(message)
        first = wcs.receive(message, complete_s + 0.02)
        # Потеря первого ACK, перезапуск отправителя в той же эпохе ОС.
        out.db.close()
        out = Outbox(root / "out.db", clock_domain=session.clock_domain)
        retry = wcs.receive(
            next(m for m in out.pending(complete_s + 0.03) if m["box_id"] == name),
            complete_s + 0.03,
        )
        assert out.acknowledge(retry)
        action = wcs.execute(message["message_id"], complete_s + 0.04)
        commands.append({"box_id": name, "action": action})
        results.append(
            {
                "box_id": name,
                "expected": ["SHARED01"],
                "message": message,
                "exact_set": {d["text"] for d in message["codes"]} == {"SHARED01"},
                "first_ack": first,
                "retry_ack": retry,
            }
        )
    pruned = pipe.prune(jobs[0].deadline + 6)
    out.db.close()
    wcs.db.close()
    if temp:
        temp.cleanup()
    return {
        "description": "Две перекрывающиеся области коробок; одинаковые значения в общем кадре; полная серия торцов и все запланированные полосы.",
        "metadata": metadata(c, missing_strip=missing_strip),
        "boxes": results,
        "commands": commands,
        "dispatch": dispatch,
        "processed_images": len(events),
        "all_captures_accepted": all(e["accepted"] for e in events),
        "stale_session_rejected": not stale["accepted"],
        "pruned_boxes": pruned,
        "retained_assignments": len(pipe.assigner.assigned),
        "limitation": "Синтетические изображения и калиброванные прямоугольные области имитатора; аппаратный захват, точность калибровки и IPC проверяются отдельно.",
    }


if __name__ == "__main__":
    result = run_replay()
    path = Path("results/replay.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    from barcode_reader.transport import canonical

    message = result["boxes"][0]["message"]
    Path("results/message_example.json").write_text(
        json.dumps(json.loads(canonical(message)), ensure_ascii=False, indent=2) + "\n"
    )
    Path("results/ack_example.json").write_text(
        json.dumps(result["boxes"][0]["first_ack"], ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"Полное множество: {sum(b['exact_set'] for b in result['boxes'])}/{len(result['boxes'])}; изображения: {result['processed_images']}"
    )
