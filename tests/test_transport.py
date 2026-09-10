import time
from copy import deepcopy

import pytest

from barcode_reader.control import FACES, BoxTracker
from barcode_reader.coverage import CaptureContract
from barcode_reader.decoder import Detection
from barcode_reader.session import Session
from barcode_reader.transport import DurableWCS, Outbox, canonical


def packet(session="boot42"):
    t = BoxTracker(Session(session, "OS1"))
    t.register(
        "B", 0, 1, 10, contract=CaptureContract.image_demo({f: "frame" for f in FACES})
    )
    d = Detection("Code 128", "12", "3132", ((0, 0), (1, 0), (1, 1), (0, 1)))
    for f in FACES:
        t.observe("B", f, "frame", 0.5, 0.6, [d] if f == "top" else [])
    return t.finalize("B", 1)


def test_restart_retry_and_receipt_are_durable(tmp_path):
    m = packet()
    out = Outbox(tmp_path / "out.db", clock_domain="OS1")
    out.put(m)
    out.db.close()
    out = Outbox(tmp_path / "out.db", clock_domain="OS1")
    assert out.pending(1) == [m]
    w = DurableWCS(tmp_path / "wcs.db", clock_domain="OS1")
    assert w.receive(m, 1)["receipt"] == "accepted"
    w.db.close()
    w = DurableWCS(tmp_path / "wcs.db", clock_domain="OS1")
    ack = w.receive(m, 2)
    assert ack["receipt"] == "duplicate"
    assert out.acknowledge(ack)
    assert out.pending(2) == []
    assert w.execute(m["message_id"], 3) == "resolve_all_values"
    assert w.execute(m["message_id"], 4) == "already_recorded"
    assert out.prune(wall_now=time.time() + 90000) == 1
    assert w.prune(20, wall_now=time.time() + 90000) == 1


def test_os_restart_quarantines_old_epoch_and_reused_box_id(tmp_path):
    old = packet()
    new = packet("new-session")
    assert old["message_id"] != new["message_id"]
    out = Outbox(tmp_path / "out.db", clock_domain="OS1")
    out.put(old)
    out.db.close()
    out = Outbox(tmp_path / "out.db", clock_domain="OS2")
    assert out.pending(1) == []
    w = DurableWCS(tmp_path / "w.db", clock_domain="OS2")
    with pytest.raises(ValueError):
        w.receive(old, 1)
    assert out.db.execute("SELECT state FROM outbox_v2").fetchone()[0] == "quarantined"


def test_late_message_and_expired_restart(tmp_path):
    m = packet()
    out = Outbox(tmp_path / "out.db", clock_domain="OS1")
    out.put(m)
    assert out.pending(11) == []
    w = DurableWCS(tmp_path / "w.db", clock_domain="OS1")
    assert w.receive(m, 11)["action"] == "exception_only"
    assert w.execute(m["message_id"], 12) == "exception_only"


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 1},
        {"codes": []},
        {"capture_complete": False},
        {"status": "no_read"},
        {"status": "late"},
        {"created_s": float("nan")},
        {"created_s": -1},
        {"deadline_s": 0.5},
        {"observed_faces": ["top"]},
        {"accepted_codes": []},
        {"session_id": "wrong"},
    ],
)
def test_wcs_rejects_contradictory_packet(tmp_path, change):
    w = DurableWCS(tmp_path / "w.db", clock_domain="OS1")
    with pytest.raises(ValueError):
        w.receive(packet() | change, 2)
    assert w.db.execute("SELECT count(*) FROM receipts_v2").fetchone()[0] == 0


def test_durable_corruption_is_quarantined_and_ack_body_is_checked(tmp_path):
    m = packet()
    out = Outbox(tmp_path / "out.db", clock_domain="OS1")
    out.put(m)
    assert not out.acknowledge(
        {"message_id": m["message_id"], "receipt": "accepted", "body_sha256": "wrong"}
    )
    out.db.execute("UPDATE outbox_v2 SET body='{}'")
    out.db.commit()
    assert out.pending(2) == []


def test_limits_and_identity_conflict(tmp_path):
    m = packet()
    with pytest.raises(ValueError):
        canonical(m | {"codes": m["codes"] * 25})
    w = DurableWCS(tmp_path / "w.db", clock_domain="OS1")
    w.receive(m, 1)
    conflicting = deepcopy(m)
    conflicting["codes"][0]["text"] = "changed"
    conflicting["accepted_codes"][0]["text"] = "changed"
    with pytest.raises(ValueError):
        w.receive(conflicting, 2)


def test_retention_keeps_idempotency_until_physical_deadline(tmp_path):
    m = packet()
    w = DurableWCS(tmp_path / "w.db", clock_domain="OS1")
    w.receive(m, 1)
    w.execute(m["message_id"], 2)
    assert w.prune(3, wall_now=time.time() + 100, retention_s=0) == 0
    assert w.receive(m, 3)["receipt"] == "duplicate"
    assert w.execute(m["message_id"], 3) == "already_recorded"
