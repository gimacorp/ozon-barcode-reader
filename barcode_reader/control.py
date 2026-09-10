"""Модель привязки результатов и идемпотентного обмена; драйверов ПЛК здесь нет."""

from dataclasses import dataclass, field
from copy import deepcopy
import math
from .decoder import Detection
from .coverage import CaptureContract, Evidence, independent_count

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


class BoxTracker:
    """Получает назначенный через Assigner ID и проверяет контракт захвата.

    Низкоуровневый observe доверяет адаптеру геометрии. Обработка изображений
    вызывает его после уникального назначения ROI в assignment.py.
    """
    def __init__(self):
        self.boxes = {}

    def register(self, box_id, entered_s, capture_end_s, deadline_s, *, contract=None):
        if box_id in self.boxes:
            raise ValueError("Повторный идентификатор коробки")
        if not all(math.isfinite(t) for t in (entered_s,capture_end_s,deadline_s)) or not entered_s <= capture_end_s < deadline_s:
            raise ValueError("Неверный порядок временных границ")
        self.boxes[box_id] = Box(box_id, entered_s, capture_end_s, deadline_s, contract=contract or CaptureContract.production(box_id))

    def observe(self, box_id, face, frame_id, captured_s, completed_s, detections, *, evidence=None, dropped_rows=()):
        if box_id not in self.boxes or face not in FACES:
            return False
        b = self.boxes[box_id]
        if (b.closed or not b.entered_s <= captured_s <= b.capture_end_s
                or not captured_s <= completed_s <= b.deadline_s):
            return False
        evidence = evidence or Evidence(face, frame_id)
        b.contract.record(face, evidence, dropped_rows)
        b.faces = b.contract.complete_faces()
        b.latest_completion_s = max(b.latest_completion_s, completed_s)
        for d in detections:
            entry = b.observations.setdefault(d.key, {"detection": d, "frames": set(), "faces": set()})
            # Повторная обработка того же кадра не является подтверждением.
            entry["frames"].add(evidence)
            entry["faces"].add(face)
        return True

    def finalize(self, box_id, now_s, confirmations=1):
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
        all_codes, accepted = [], []
        for key in sorted(b.observations):
            e = b.observations[key]
            d = e["detection"]
            item = {"format": d.format, "text": d.text, "payload_hex": d.payload_hex,
                    "confirmations": independent_count(e["frames"]), "faces": sorted(e["faces"])}
            all_codes.append(item)
            if independent_count(e["frames"]) >= confirmations:
                accepted.append(item)
        status = ("late" if now_s > b.deadline_s else "incomplete_views" if b.faces != FACES
                  else "no_read" if not all_codes else "unconfirmed" if len(accepted) != len(all_codes)
                  else "read")
        return {"schema_version": 1, "message_id": f"{box_id}:1", "box_id": box_id,
                "status": status, "codes": all_codes, "accepted_codes": accepted,
                "observed_faces": sorted(b.faces), "capture_complete": b.faces == FACES, "deadline_s": b.deadline_s,
                "complete_set_verified": False}


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
        action = "lookup_all_codes" if message["status"] == "read" and now_s <= message["deadline_s"] else "exception_lane"
        self.commands.append({"box_id": message["box_id"], "action": action})
        self.receipts[key] = {"message": deepcopy(message), "action": action}
        return {"message_id": key, "ack": "accepted", "action": action}
