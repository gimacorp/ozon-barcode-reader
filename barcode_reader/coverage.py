"""Покрытие связывается с коробкой, сессией, камерой и исходным захватом."""

import math
from dataclasses import dataclass, field
from typing import Iterable

LINE_FACES = frozenset({"top", "bottom", "left", "right"})


def row_spans(total: int, rows: int, overlap: int) -> tuple[tuple[int, int], ...]:
    if total <= 0 or not 0 <= overlap < rows:
        raise ValueError("Требуется total > 0 и rows > overlap >= 0")
    spans = []
    start = 0
    while start < total:
        spans.append((start, min(start + rows, total)))
        if start + rows >= total:
            break
        start += rows - overlap
    return tuple(spans)


@dataclass(frozen=True)
class Evidence:
    camera: str
    acquisition: str
    rows: tuple[int, int] | None = None
    session_id: str = ""
    box_id: str = ""

    @property
    def source(self) -> tuple[str, str, str, str]:
        return self.session_id, self.box_id, self.camera, self.acquisition


@dataclass
class CaptureContract:
    area_frames: dict[str, set[str]] = field(default_factory=dict)
    line_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    cameras: dict[str, str] = field(default_factory=dict)
    scans: dict[str, str] = field(default_factory=dict)
    required_chunks: dict[str, set[tuple[int, int]]] = field(default_factory=dict)
    session_id: str = ""
    box_id: str = ""
    processed_frames: dict[str, set[str]] = field(default_factory=dict)
    processed_rows: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    processed_chunks: dict[str, set[tuple[int, int]]] = field(default_factory=dict)

    @classmethod
    def production(
        cls,
        box_id: str,
        total_rows: int = 7200,
        *,
        session_id: str,
        frame_count: int = 5,
        strip_rows: int = 2048,
        overlap: int = 1024,
        cameras: dict[str, str] | None = None,
        area_frames: dict[str, set[str]] | None = None,
    ) -> "CaptureContract":
        faces = LINE_FACES | {"front", "rear"}
        return cls(
            area_frames=area_frames
            or {
                f: {f"{box_id}-{f}-{i}" for i in range(frame_count)}
                for f in ("front", "rear")
            },
            line_ranges={f: (0, total_rows) for f in LINE_FACES},
            cameras=cameras or {f: f for f in faces},
            scans={f: f"{box_id}-{f}-scan" for f in LINE_FACES},
            required_chunks={
                f: set(row_spans(total_rows, strip_rows, overlap)) for f in LINE_FACES
            },
            session_id=session_id,
            box_id=box_id,
        )

    @classmethod
    def from_config(
        cls, box_id: str, config: dict, *, session_id: str
    ) -> "CaptureContract":
        return cls.production(
            box_id,
            math.ceil(
                config["box_length_mm"] * config["line_rate_hz"] / config["speed_mm_s"]
            ),
            session_id=session_id,
            frame_count=config["area_frames_per_box"],
            strip_rows=config["line_strip_rows"],
            overlap=config["line_strip_overlap_rows"],
        )

    @classmethod
    def image_demo(cls, frame_ids: dict[str, str]) -> "CaptureContract":
        return cls(
            area_frames={f: {fid} for f, fid in frame_ids.items()},
            cameras={f: f for f in frame_ids},
        )

    def bind(self, session_id: str, box_id: str) -> None:
        if self.session_id and (self.session_id, self.box_id) != (session_id, box_id):
            raise ValueError("Контракт относится к другой коробке или сессии")
        self.session_id, self.box_id = session_id, box_id

    def accepts(self, face: str, evidence: Evidence) -> bool:
        if (evidence.session_id, evidence.box_id, evidence.camera) != (
            self.session_id,
            self.box_id,
            self.cameras.get(face),
        ):
            return False
        if face in self.area_frames:
            return (
                evidence.rows is None and evidence.acquisition in self.area_frames[face]
            )
        return (
            face in self.line_ranges
            and evidence.acquisition == self.scans[face]
            and evidence.rows in self.required_chunks[face]
        )

    def record(
        self, face: str, evidence: Evidence, dropped_rows: Iterable[int] = ()
    ) -> bool:
        if not self.accepts(face, evidence):
            return False
        if evidence.rows is None:
            self.processed_frames.setdefault(face, set()).add(evidence.acquisition)
        else:
            start, end = evidence.rows
            self.processed_chunks.setdefault(face, set()).add(evidence.rows)
            cursor = start
            intervals = self.processed_rows.setdefault(face, [])
            for row in sorted(set(dropped_rows)):
                if start <= row < end:
                    intervals.append((cursor, row))
                    cursor = row + 1
            intervals.append((cursor, end))
            # Повтор фрагмента сохраняет ограниченное число объединённых интервалов.
            merged = []
            for a, b in sorted(intervals):
                if a == b:
                    continue
                if merged and a <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
                else:
                    merged.append((a, b))
            self.processed_rows[face] = merged
        return True

    def complete_faces(self) -> set[str]:
        result = {
            f
            for f, ids in self.area_frames.items()
            if ids <= self.processed_frames.get(f, set())
        }
        for face, (start, end) in self.line_ranges.items():
            if not self.required_chunks[face] <= self.processed_chunks.get(face, set()):
                continue
            intervals = self.processed_rows.get(face, [])
            if any(a <= start and b >= end for a, b in intervals):
                result.add(face)
        return result


def independent_count(evidence: Iterable[Evidence]) -> int:
    """Максимум непересекающихся диапазонов каждого исходного захвата."""
    groups = {}
    for item in evidence:
        groups.setdefault(item.source, set()).add(item.rows)
    total = 0
    for intervals in groups.values():
        if None in intervals:
            total += 1
            continue
        end = -1
        for a, b in sorted(intervals, key=lambda r: r[1]):
            if a >= end:
                total += 1
                end = b
    return total
