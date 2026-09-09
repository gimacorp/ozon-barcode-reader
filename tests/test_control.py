import pytest
from barcode_reader.control import BoxTracker,MockPLC,FACES
from barcode_reader.decoder import Detection

D=Detection("Code 128","VALUE",b"VALUE".hex(),((0,0),(10,0),(10,10),(0,10)))


def tracker():
    t=BoxTracker();t.register("A",0,2,3)
    return t


def complete(t,ds=(D,)):
    for face in FACES:t.observe("A",face,"frame-1",1,1.2,ds if face=="top" else [])


def test_box_ids_do_not_mix():
    t=tracker();t.register("B",2,4,5)
    assert not t.observe("B","top","old",1,2.1,[D])
    assert not t.observe(None,"top","new",2.2,2.3,[D])
    assert not t.boxes["B"].observations


def test_exact_deadline_and_closed_result():
    t=tracker();complete(t)
    assert t.observe("A","top","last",2,3,[D])
    assert not t.observe("A","top","late",2,3.0001,[D])
    assert t.finalize("A",3)["status"]=="read"
    assert not t.observe("A","top","later",2,3,[D])
    with pytest.raises(ValueError):t.finalize("A",3)


def test_same_frame_is_not_confirmation():
    t=tracker();complete(t)
    t.observe("A","top","frame-1",1,1.2,[D])
    msg=t.finalize("A",2.5,confirmations=2)
    assert msg["status"]=="unconfirmed"
    assert len(msg["codes"])==1 and msg["codes"][0]["confirmations"]==1


@pytest.mark.parametrize("mode,expected",[("empty","no_read"),("missing","incomplete_views"),("late","late")])
def test_exception_states(mode,expected):
    t=tracker()
    if mode!="missing":complete(t,[] if mode=="empty" else [D])
    assert t.finalize("A",3.1 if mode=="late" else 2.5)["status"]==expected


def test_no_false_promise_of_completeness():
    t=tracker();complete(t)
    assert t.finalize("A",2.5)["complete_set_verified"] is False


def test_idempotent_plc_and_conflicting_retry():
    t=tracker();complete(t);msg=t.finalize("A",2.5)
    plc=MockPLC()
    assert plc.receive(msg,2.6)["ack"]=="accepted"
    assert plc.receive(msg,2.7)["ack"]=="duplicate"
    assert len(plc.commands)==1
    with pytest.raises(ValueError):plc.receive(msg|{"status":"late"},2.7)


def test_late_transport_goes_to_exception():
    t=tracker();complete(t);msg=t.finalize("A",2.5)
    assert MockPLC().receive(msg,3.1)["action"]=="exception_lane"


def test_bad_time_and_early_finalization():
    t=tracker()
    with pytest.raises(ValueError):t.register("X",0,3,2)
    with pytest.raises(ValueError):t.finalize("A",1)


def test_finalization_waits_for_completed_decoding():
    t=tracker()
    t.observe("A","top","f1",1.9,2.9,[D])
    with pytest.raises(ValueError):t.finalize("A",2.1)
    assert t.finalize("A",2.9)["codes"][0]["text"] == "VALUE"


def test_plc_keeps_immutable_receipt_snapshot():
    t=tracker();complete(t);message=t.finalize("A",2.5)
    plc=MockPLC();plc.receive(message,2.6)
    message["codes"][0]["text"]="CHANGED"
    with pytest.raises(ValueError):plc.receive(message,2.7)
    assert plc.receipts["A:1"]["message"]["codes"][0]["text"]=="VALUE"
