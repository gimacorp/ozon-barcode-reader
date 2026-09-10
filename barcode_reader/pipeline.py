"""Граница интеграции: изображение → ROI → коробка → покрытие → результат."""

from dataclasses import dataclass

import numpy as np

from .assignment import Assigner, FaceRegion
from .control import BoxTracker
from .coverage import Evidence
from .decoder import decode


@dataclass
class Capture:
    image: np.ndarray
    session_id: str
    camera: str
    acquisition: str
    regions: list[FaceRegion]
    image_to_face: np.ndarray
    captured_s: float
    completed_s: float
    rows: tuple[int, int] | None = None
    dropped_rows: tuple[int, ...] = ()


class Pipeline:
    def __init__(self, tracker: BoxTracker, *, formats: str = "Code128"):
        self.tracker = tracker
        self.assigner = Assigner()
        self.formats = formats

    def process(self, capture: Capture) -> dict:
        if capture.session_id != self.tracker.session.session_id:
            return {"accepted": False, "reason": "stale_session"}
        if capture.rows and capture.image.shape[0] != capture.rows[1] - capture.rows[0]:
            raise ValueError("Высота изображения противоречит диапазону строк")
        if not capture.regions:
            return {"accepted": False, "reason": "missing_regions"}
        eligible = []
        for region in capture.regions:
            box = self.tracker.boxes.get(region.box_id)
            evidence = Evidence(
                capture.camera,
                capture.acquisition,
                capture.rows,
                capture.session_id,
                region.box_id,
            )
            if (
                box is None
                or box.closed
                or not box.contract.accepts(region.face, evidence)
                or not box.entered_s <= capture.captured_s <= box.capture_end_s
                or not capture.captured_s <= capture.completed_s <= box.deadline_s
            ):
                return {"accepted": False, "reason": "unexpected_capture"}
            eligible.append((region, evidence))
        detections = decode(capture.image, formats=self.formats)
        ambiguous = 0
        for index, detection in enumerate(detections):
            owner = self.assigner.assign(
                capture.camera,
                capture.acquisition,
                f"{capture.rows}:{index}",
                detection.polygon,
                capture.image_to_face,
                capture.regions,
            )
            if owner is None:
                ambiguous += 1
                for region, _ in eligible:
                    self.tracker.boxes[region.box_id].ambiguous = True
                continue
            region, evidence = next(
                (r, e) for r, e in eligible if (r.box_id, r.face) == owner
            )
            self.tracker.observe(
                region.box_id,
                region.face,
                capture.acquisition,
                capture.captured_s,
                capture.completed_s,
                [detection],
                evidence=evidence,
                mark_capture=False,
            )
        for region, evidence in eligible:
            self.tracker.observe(
                region.box_id,
                region.face,
                capture.acquisition,
                capture.captured_s,
                capture.completed_s,
                [],
                evidence=evidence,
                dropped_rows=capture.dropped_rows,
            )
        return {"accepted": True, "detections": len(detections), "ambiguous": ambiguous}

    def prune(self, now_s: float, retention_s: float = 5.0) -> int:
        removed = self.tracker.prune(now_s, retention_s)
        self.assigner.release_boxes(removed)
        return len(removed)
