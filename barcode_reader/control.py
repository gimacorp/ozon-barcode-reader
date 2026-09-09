"""Модель привязки результатов и идемпотентного обмена; драйверов ПЛК здесь нет."""

from dataclasses import dataclass, field
from copy import deepcopy
import math
from .decoder import Detection

FACES = frozenset({"top", "bottom", "left", "right", "front", "rear"})


@dataclass
class Box:
    box_id: str
    entered_s: float
    capture_end_s: float
    deadline_s: float
    faces: set = field(default_factory=set)
    observations: dict = field(default_factory=dict)
    closed: bool = False
    latest_completion_s: float = -math.inf


class BoxTracker:
    """Идентификатор задаёт имитатор аппаратного трекинга, а не декодер.

    В промышленной версии ID определяется фотофронтом и энкодером. При двух
    коробках в кадре требуется геометрическая привязка ROI; этот адаптер ещё
    предстоит реализовать. Здесь неоднозначный ID отвергается явно.
    """
    def __init__(self):
        self.boxes = {}

    def register(self, box_id, entered_s, capture_end_s, deadline_s):
        if box_id in self.boxes:
            raise ValueError("Повторный идентификатор коробки")
        if not all(math.isfinite(t) for t in (entered_s,capture_end_s,deadline_s)) or not entered_s <= capture_end_s < deadline_s:
            raise ValueError("Неверный порядок временных границ")
        self.boxes[box_id] = Box(box_id, entered_s, capture_end_s, deadline_s)

    def observe(self, box_id, face, frame_id, captured_s, completed_s, detections):
        if box_id not in self.boxes or face not in FACES:
            return False
        b = self.boxes[box_id]
        if (b.closed or not b.entered_s <= captured_s <= b.capture_end_s
                or not captured_s <= completed_s <= b.deadline_s):
            return False
        b.faces.add(face)
        b.latest_completion_s = max(b.latest_completion_s, completed_s)
        for d in detections:
            entry = b.observations.setdefault(d.key, {"detection": d, "frames": set(), "faces": set()})
            # Повторная обработка того же кадра не является подтверждением.
            entry["frames"].add((face, frame_id))
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
                    "confirmations": len(e["frames"]), "faces": sorted(e["faces"])}
            all_codes.append(item)
            if len(e["frames"]) >= confirmations:
                accepted.append(item)
        status = ("late" if now_s > b.deadline_s else "incomplete_views" if b.faces != FACES
                  else "no_read" if not all_codes else "unconfirmed" if len(accepted) != len(all_codes)
                  else "read")
        return {"schema_version": 1, "message_id": f"{box_id}:1", "box_id": box_id,
                "status": status, "codes": all_codes, "accepted_codes": accepted,
                "observed_faces": sorted(b.faces), "deadline_s": b.deadline_s,
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
