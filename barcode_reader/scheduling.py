"""Расписание камер из общего конфига и ограниченная очередь EDF."""

import heapq
import math
from collections.abc import Callable
from dataclasses import dataclass

from .coverage import row_spans
from .engineering import load_config, working_distance


@dataclass(frozen=True)
class Job:
    box: int
    kind: str
    arrival: float
    deadline: float
    channel: str
    sequence: int
    captured_s: float = 0.0
    rows: tuple[int, int] | None = None


def arrivals(
    boxes: int = 100, interval: float | None = None, *, config: dict | None = None
) -> list[Job]:
    c = config or load_config("configs/conveyor.json")
    v = c["speed_mm_s"]
    interval = c["leading_edge_interval_s"] if interval is None else interval
    total = math.ceil(c["box_length_mm"] * c["line_rate_hz"] / v)
    spans = row_spans(total, c["line_strip_rows"], c["line_strip_overlap_rows"])
    wd = working_distance(
        c["area_focal_length_mm"],
        c["area_pixels_x"] * c["area_sensor_pixel_um"] / 1000,
        c["area_fov_width_mm"],
    )
    camera_dx = math.sqrt(wd**2 - c["area_elevation_mm"] ** 2)
    result = []
    for box in range(boxes):
        base = box * interval
        deadline = base + c["sorter_x_mm"] / v - c["plc_actuation_s"] - c["guard_s"]
        for channel, x in c["line_positions_mm"].items():
            for i, span in enumerate(spans):
                captured = base + x / v + span[1] / c["line_rate_hz"]
                result.append(
                    Job(
                        box,
                        "line",
                        captured + c["line_transfer_s"],
                        deadline,
                        channel,
                        i,
                        captured,
                        span,
                    )
                )
        count = c["area_frames_per_box"]
        for channel, delay in [("front", 0), ("rear", c["box_length_mm"] / v)]:
            for i in range(count):
                # Худшая положительная фаза: полшага временной сетки.
                captured = (
                    base
                    + (c["rear_camera_x_mm"] + camera_dx) / v
                    + delay
                    + (i - (count - 1) / 2 + 0.5) / c["area_frame_rate_hz"]
                )
                result.append(
                    Job(
                        box,
                        "area",
                        captured + c["area_transfer_s"],
                        deadline,
                        channel,
                        i,
                        captured,
                    )
                )
    return sorted(result, key=lambda job: job.arrival)


def simulate(
    jobs: list[Job],
    service: Callable[[Job], float],
    workers: int = 8,
    capacity: int = 64,
    *,
    delivery_s: float = 0.05,
) -> dict:
    """EDF; переполнение или невозможный срок отменяют остаток задач коробки."""
    if workers < 1 or capacity < 1 or delivery_s < 0:
        raise ValueError("Некорректные параметры очереди")
    pending, active, finished, cancelled, waits = [], [], {}, set(), []
    i = serial = maxq = 0
    while i < len(jobs) or active or pending:
        now = min(
            jobs[i].arrival if i < len(jobs) else math.inf,
            active[0][0] if active else math.inf,
        )
        while active and active[0][0] <= now:
            end, _, job = heapq.heappop(active)
            finished[job.box] = max(finished.get(job.box, 0), end)
        while i < len(jobs) and jobs[i].arrival <= now:
            job = jobs[i]
            i += 1
            if len(pending) >= capacity:
                cancelled.add(job.box)
            else:
                heapq.heappush(pending, (job.deadline, serial, job))
                serial += 1
        while pending and len(active) < workers:
            _, seq, job = heapq.heappop(pending)
            duration = service(job)
            if job.box in cancelled or now + duration + delivery_s > job.deadline:
                cancelled.add(job.box)
                continue
            waits.append(now - job.arrival)
            heapq.heappush(active, (now + duration, seq, job))
        maxq = max(maxq, len(pending))
    deadlines = {job.box: job.deadline for job in jobs}
    outcomes = [
        {
            "box": box,
            "ack_s": finished.get(box, 0) + delivery_s,
            "late": box in cancelled or finished.get(box, 0) + delivery_s > deadline,
        }
        for box, deadline in sorted(deadlines.items())
    ]
    return {
        "outcomes": outcomes,
        "max_queue": maxq,
        "max_wait_s": max(waits, default=0),
        "cancelled_boxes": len(cancelled),
    }
