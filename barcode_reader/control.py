"""Модель привязки результатов и идемпотентного обмена; драйверов ПЛК здесь нет."""

import math
from copy import deepcopy
from dataclasses import dataclass, field

from .coverage import CaptureContract, Evidence, independent_count
from .decoder import Detection
from .engineering import load_config
from .session import Session

FACES = frozenset({"top", "bottom", "left", "right", "front", "rear"})


@dataclass
class Box:
    box_id: str
    entered_s: float
    capture_end_s: float
    deadline_s: float
    faces: set = field(default_factory=set)
    observations: dict = field(default_factory=dict)
    contract: CaptureContract | None = None
    closed: bool = False
    latest_completion_s: float = -math.inf
    closed_s: float | None = None
    sequence: int = 0
    ambiguous: bool = False


class BoxTracker:
    """Получает назначенный через Assigner ID и проверяет контракт захвата.

    Низкоуровневый observe доверяет адаптеру геометрии. Обработка изображений
    вызывает его после уникального назначения ROI в assignment.py.
    """

    def __init__(self, session: Session | None = None, *, config: dict | None = None):
        self.config = config or load_config()
        self.session = session or Session()
        self.boxes: dict[str, Box] = {}
        self.sequence = 0

    def register(
        self,
        box_id: str,
        entered_s: float,
        capture_end_s: float,
        deadline_s: float,
        *,
        contract: CaptureContract | None = None,
    ) -> None:
        if len(self.boxes) >= 64:
            raise OverflowError(
                "Ёмкость реестра исчерпана; требуется финализация и prune"
            )
        if box_id in self.boxes:
            raise ValueError("Повторный идентификатор коробки")
        if (
            not all(math.isfinite(t) for t in (entered_s, capture_end_s, deadline_s))
            or not entered_s <= capture_end_s < deadline_s
        ):
            raise ValueError("Неверный порядок временных границ")
        contract = contract or CaptureContract.from_config(
            box_id, self.config, session_id=self.session.session_id
        )
        contract.bind(self.session.session_id, box_id)
        self.sequence += 1
        self.boxes[box_id] = Box(
            box_id,
            entered_s,
            capture_end_s,
            deadline_s,
            contract=contract,
            sequence=self.sequence,
        )

    def observe(
        self,
        box_id: str,
        face: str,
        frame_id: str,
        captured_s: float,
        completed_s: float,
        detections: list[Detection],
        *,
        evidence: Evidence | None = None,
        dropped_rows: tuple[int, ...] = (),
        mark_capture: bool = True,
    ) -> bool:
        if box_id not in self.boxes or face not in FACES:
            return False
        b = self.boxes[box_id]
        if (
            b.closed
            or not b.entered_s <= captured_s <= b.capture_end_s
            or not captured_s <= completed_s <= b.deadline_s
        ):
            return False
        evidence = evidence or Evidence(
            face, frame_id, session_id=self.session.session_id, box_id=box_id
        )
        if not b.contract.accepts(face, evidence):
            return False
        if mark_capture:
            b.contract.record(face, evidence, dropped_rows)
        b.faces = b.contract.complete_faces()
        b.latest_completion_s = max(b.latest_completion_s, completed_s)
        for d in detections:
            entry = b.observations.setdefault(
                d.key, {"detection": d, "frames": set(), "faces": set()}
            )
            # Повторная обработка того же кадра не является подтверждением.
            entry["frames"].add(evidence)
            entry["faces"].add(face)
        return True

    def finalize(self, box_id: str, now_s: float, confirmations: int = 1) -> dict:
        if confirmations < 1:
            raise ValueError("Нужно хотя бы одно подтверждение")
        b = self.boxes[box_id]
        if b.closed:
            raise ValueError("Результат уже зафиксирован")
        if not math.isfinite(now_s) or now_s < b.capture_end_s:
            raise ValueError("Сбор кадров ещё не завершён")
        if now_s < b.latest_completion_s:
            raise ValueError("Время финализации предшествует завершению декодирования")
        b.closed = True
        b.closed_s = now_s
        all_codes, accepted = [], []
        for key in sorted(b.observations):
            e = b.observations[key]
            d = e["detection"]
            item = {
                "format": d.format,
                "text": d.text,
                "payload_hex": d.payload_hex,
                "confirmations": independent_count(e["frames"]),
                "faces": sorted(e["faces"]),
            }
            all_codes.append(item)
            if independent_count(e["frames"]) >= confirmations:
                accepted.append(item)
        status = (
            "late"
            if now_s > b.deadline_s
            else "incomplete_views"
            if b.faces != FACES
            else "ambiguous_assignment"
            if b.ambiguous
            else "no_read"
            if not all_codes
            else "unconfirmed"
            if len(accepted) != len(all_codes)
            else "read"
        )
        return {
            "schema_version": 2,
            "message_id": f"{self.session.session_id}:{box_id}:{b.sequence}",
            "box_id": box_id,
            "session_id": self.session.session_id,
            "clock_domain": self.session.clock_domain,
            "created_s": now_s,
            "status": status,
            "codes": all_codes,
            "accepted_codes": accepted,
            "observed_faces": sorted(b.faces),
            "capture_complete": b.faces == FACES,
            "deadline_s": b.deadline_s,
            "complete_set_verified": False,
        }

    def prune(self, now_s: float, retention_s: float = 5.0) -> set[str]:
        """Удаляет закрытые треки после срока и окна диагностического хранения."""
        removed = {
            key
            for key, box in self.boxes.items()
            if box.closed_s is not None
            and now_s >= max(box.closed_s, box.deadline_s) + retention_s
        }
        for key in removed:
            del self.boxes[key]
        return removed


class MockPLC:
    """Имитатор приёмника: повтор безопасен; просроченная команда не сортирует."""

    def __init__(self):
        self.receipts = {}
        self.commands = []

    def receive(self, message, now_s):
        key = message["message_id"]
        if key in self.receipts:
            if self.receipts[key]["message"] != message:
                raise ValueError("Один message_id содержит разные данные")
            return {"message_id": key, "ack": "duplicate"}
        if not math.isfinite(now_s):
            raise ValueError("Некорректное время")
        # Маршрут определяет WCS/ПЛК по всем кодам; reader его не выдумывает.
        action = (
            "lookup_all_codes"
            if message["status"] == "read" and now_s <= message["deadline_s"]
            else "exception_lane"
        )
        self.commands.append({"box_id": message["box_id"], "action": action})
        self.receipts[key] = {"message": deepcopy(message), "action": action}
        return {"message_id": key, "ack": "accepted", "action": action}
