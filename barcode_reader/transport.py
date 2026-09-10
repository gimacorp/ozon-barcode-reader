"""Строгий пакет v2 и журналы доставки в пределах эпохи часов ОС."""

import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from .control import FACES
from .session import system_clock_domain

MAX_CODES = 24
MAX_PAYLOAD_BYTES = 128
MAX_MESSAGE_BYTES = 16384
STATUSES = {
    "read",
    "no_read",
    "incomplete_views",
    "unconfirmed",
    "late",
    "ambiguous_assignment",
}


def finite_time(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def validate_message(message: dict) -> None:
    """Проверяет данные на границе WCS, включая согласованность результата."""
    required = {
        "schema_version",
        "message_id",
        "session_id",
        "clock_domain",
        "box_id",
        "created_s",
        "deadline_s",
        "status",
        "codes",
        "accepted_codes",
        "observed_faces",
        "capture_complete",
        "complete_set_verified",
    }
    if not isinstance(message, dict) or not required <= message.keys():
        raise ValueError("Неполный пакет v2")
    if type(message["schema_version"]) is not int or message["schema_version"] != 2:
        raise ValueError("Требуется схема v2")
    for name in ("message_id", "session_id", "clock_domain", "box_id"):
        if not isinstance(message[name], str) or not 0 < len(message[name]) <= 256:
            raise ValueError("Некорректный идентификатор")
    prefix = f"{message['session_id']}:{message['box_id']}:"
    suffix = message["message_id"].removeprefix(prefix)
    if (
        not message["message_id"].startswith(prefix)
        or not suffix.isdigit()
        or int(suffix) < 1
    ):
        raise ValueError("message_id не соответствует сессии и коробке")
    if not all(finite_time(message[k]) for k in ("created_s", "deadline_s")):
        raise ValueError("Некорректное время")
    if message["status"] not in STATUSES:
        raise ValueError("Неизвестный статус")
    if (
        type(message["capture_complete"]) is not bool
        or message["complete_set_verified"] is not False
    ):
        raise ValueError("Некорректное утверждение о полноте")
    faces = message["observed_faces"]
    if (
        not isinstance(faces, list)
        or any(f not in FACES for f in faces)
        or len(set(faces)) != len(faces)
    ):
        raise ValueError("Некорректные грани")
    if message["capture_complete"] != (set(faces) == FACES):
        raise ValueError("Полнота захвата противоречит граням")
    code_keys = []
    for field in ("codes", "accepted_codes"):
        values = message[field]
        if not isinstance(values, list) or len(values) > MAX_CODES:
            raise ValueError("Превышен лимит значений")
        keys = []
        for value in values:
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("format"), str)
                or not value["format"]
            ):
                raise ValueError("Некорректная символика")
            try:
                payload = bytes.fromhex(value["payload_hex"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Некорректные исходные байты") from error
            if (
                not 0 < len(payload) <= MAX_PAYLOAD_BYTES
                or payload.hex() != value["payload_hex"]
            ):
                raise ValueError("Требуется каноническое hex-представление 1–128 байт")
            keys.append((value["format"], value["payload_hex"]))
        if len(set(keys)) != len(keys):
            raise ValueError("Повтор ключа значения")
        code_keys.append(set(keys))
    codes, accepted = code_keys
    if not accepted <= codes or any(
        v not in message["codes"] for v in message["accepted_codes"]
    ):
        raise ValueError("Подтверждённые значения отсутствуют в результате")
    status = message["status"]
    complete = message["capture_complete"]
    late = message["created_s"] > message["deadline_s"]
    valid = {
        "read": complete and bool(codes) and accepted == codes and not late,
        "no_read": complete and not codes and not late,
        "incomplete_views": not complete and not late,
        "unconfirmed": complete and bool(codes) and accepted != codes and not late,
        "late": late,
        "ambiguous_assignment": complete and not late,
    }
    if not valid[status]:
        raise ValueError("Статус противоречит времени, захвату или кодам")


def canonical(message: dict) -> str:
    validate_message(message)
    body = json.dumps(
        message,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(body.encode()) > MAX_MESSAGE_BYTES:
        raise ValueError("Пакет слишком большой")
    return body


def digest(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


class Outbox:
    def __init__(self, path: str | Path, *, clock_domain: str | None = None):
        self.clock_domain = clock_domain or system_clock_domain()
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS outbox_v2 (id TEXT PRIMARY KEY, body TEXT NOT NULL, deadline REAL NOT NULL, clock TEXT NOT NULL, state TEXT NOT NULL, terminal_wall REAL)"
        )
        with self.db:
            self.db.execute(
                "UPDATE outbox_v2 SET state='quarantined', terminal_wall=? WHERE state='pending' AND clock!=?",
                (time.time(), self.clock_domain),
            )

    def put(self, message: dict) -> None:
        body = canonical(message)
        if message["clock_domain"] != self.clock_domain:
            raise ValueError("Пакет относится к другой эпохе часов")
        old = self.db.execute(
            "SELECT body FROM outbox_v2 WHERE id=?", (message["message_id"],)
        ).fetchone()
        if old and old[0] != body:
            raise ValueError("Конфликт message_id")
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO outbox_v2(id,body,deadline,clock,state) VALUES (?,?,?,?,'pending')",
                (message["message_id"], body, message["deadline_s"], self.clock_domain),
            )

    def pending(self, now: float) -> list[dict]:
        if not finite_time(now):
            raise ValueError("Некорректное время")
        with self.db:
            self.db.execute(
                "UPDATE outbox_v2 SET state='expired', terminal_wall=? WHERE state='pending' AND deadline<?",
                (time.time(), now),
            )
        result = []
        for mid, body in self.db.execute(
            "SELECT id,body FROM outbox_v2 WHERE state='pending' AND clock=? ORDER BY deadline",
            (self.clock_domain,),
        ).fetchall():
            try:
                message = json.loads(body)
                canonical(message)
                if (
                    message["clock_domain"] != self.clock_domain
                    or message["created_s"] > now
                ):
                    raise ValueError("Несогласованные часы журнала")
                result.append(message)
            except (ValueError, TypeError):
                with self.db:
                    self.db.execute(
                        "UPDATE outbox_v2 SET state='quarantined', terminal_wall=? WHERE id=?",
                        (time.time(), mid),
                    )
        return result

    def acknowledge(self, ack: dict) -> bool:
        row = self.db.execute(
            "SELECT body FROM outbox_v2 WHERE id=? AND state='pending'",
            (ack.get("message_id"),),
        ).fetchone()
        if (
            not row
            or ack.get("receipt") not in ("accepted", "duplicate")
            or ack.get("body_sha256") != digest(row[0])
        ):
            return False
        with self.db:
            self.db.execute(
                "UPDATE outbox_v2 SET state='acked', terminal_wall=? WHERE id=?",
                (time.time(), ack["message_id"]),
            )
        return True

    def prune(
        self, *, wall_now: float | None = None, retention_s: float = 86400
    ) -> int:
        """Удаляет терминальные записи спустя сутки; pending сохраняется до обработки срока."""
        cutoff = (time.time() if wall_now is None else wall_now) - retention_s
        with self.db:
            count = self.db.execute(
                "DELETE FROM outbox_v2 WHERE state!='pending' AND terminal_wall<=?",
                (cutoff,),
            ).rowcount
        return count


class DurableWCS:
    """ACK подтверждает запись. execute записывает намерение сортировки в имитаторе."""

    def __init__(self, path: str | Path, *, clock_domain: str | None = None):
        self.clock_domain = clock_domain or system_clock_domain()
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS receipts_v2 (id TEXT PRIMARY KEY, body TEXT NOT NULL, action TEXT NOT NULL, clock TEXT NOT NULL, deadline REAL NOT NULL, executed INTEGER DEFAULT 0, terminal_wall REAL)"
        )
        with self.db:
            self.db.execute(
                "UPDATE receipts_v2 SET action='exception_only', executed=1, terminal_wall=? WHERE clock!=? AND executed=0",
                (time.time(), self.clock_domain),
            )

    def receive(self, message: dict, now: float) -> dict:
        if not finite_time(now):
            raise ValueError("Некорректное время")
        body = canonical(message)
        mid = message["message_id"]
        if message["clock_domain"] != self.clock_domain or message["created_s"] > now:
            raise ValueError("Несогласованная эпоха или время сообщения")
        old = self.db.execute(
            "SELECT body,action FROM receipts_v2 WHERE id=?", (mid,)
        ).fetchone()
        if old:
            if old[0] != body:
                raise ValueError("Конфликт message_id")
            return {
                "message_id": mid,
                "receipt": "duplicate",
                "body_sha256": digest(body),
                "sorting": "pending_or_recorded",
            }
        action = (
            "resolve_all_values"
            if now <= message["deadline_s"] and message["status"] == "read"
            else "exception_only"
        )
        with self.db:
            self.db.execute(
                "INSERT INTO receipts_v2(id,body,action,clock,deadline) VALUES (?,?,?,?,?)",
                (mid, body, action, self.clock_domain, message["deadline_s"]),
            )
        return {
            "message_id": mid,
            "receipt": "accepted",
            "body_sha256": digest(body),
            "sorting": "pending",
            "action": action,
        }

    def execute(self, message_id: str, now: float) -> str:
        if not finite_time(now):
            raise ValueError("Некорректное время")
        row = self.db.execute(
            "SELECT body,action,executed,clock FROM receipts_v2 WHERE id=?",
            (message_id,),
        ).fetchone()
        if not row:
            raise KeyError(message_id)
        msg = json.loads(row[0])
        canonical(msg)
        if row[2]:
            return "already_recorded"
        if now < msg["created_s"]:
            raise ValueError("Выполнение предшествует созданию сообщения")
        action = (
            row[1]
            if row[3] == self.clock_domain and now <= msg["deadline_s"]
            else "exception_only"
        )
        with self.db:
            self.db.execute(
                "UPDATE receipts_v2 SET executed=1,action=?,terminal_wall=? WHERE id=?",
                (action, time.time(), message_id),
            )
        return action

    def prune(
        self, now: float, *, wall_now: float | None = None, retention_s: float = 86400
    ) -> int:
        wall = time.time() if wall_now is None else wall_now
        with self.db:
            self.db.execute(
                "UPDATE receipts_v2 SET executed=1,action='exception_only',terminal_wall=? WHERE executed=0 AND deadline<?",
                (wall, now),
            )
            count = self.db.execute(
                "DELETE FROM receipts_v2 WHERE executed=1 AND terminal_wall<=? AND (deadline<? OR clock!=?)",
                (wall - retention_s, now, self.clock_domain),
            ).rowcount
        return count
