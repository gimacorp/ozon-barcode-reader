import pytest
from barcode_reader.transport import Outbox,DurableWCS,canonical

M={'message_id':'boot42:B:1','box_id':'B','deadline_s':10.,'status':'read','codes':[{'format':'Code 128','payload_hex':'3132'}]}

def test_restart_retry_and_receipt_are_durable(tmp_path):
    out=Outbox(tmp_path/'out.db');out.put(M);out.db.close()
    out=Outbox(tmp_path/'out.db');assert out.pending(1)==[M]
    w=DurableWCS(tmp_path/'wcs.db');assert w.receive(M,1)['receipt']=='accepted';w.db.close()
    w=DurableWCS(tmp_path/'wcs.db');ack=w.receive(M,2);assert ack['receipt']=='duplicate'
    out.acknowledge(ack);assert out.pending(2)==[]
    assert w.execute(M['message_id'],3)=='resolve_all_values'
    assert w.execute(M['message_id'],4)=='already_recorded'


def test_late_message_and_expired_restart(tmp_path):
    out=Outbox(tmp_path/'out.db');out.put(M);assert out.pending(11)==[]
    w=DurableWCS(tmp_path/'w.db');assert w.receive(M,11)['action']=='exception_only'
    assert w.execute(M['message_id'],12)=='exception_only'


def test_limits_and_identity_conflict(tmp_path):
    with pytest.raises(ValueError):canonical(M|{'codes':M['codes']*25})
    with pytest.raises(ValueError):canonical(M|{'codes':[{'payload_hex':'00'*129}]})
    w=DurableWCS(tmp_path/'w.db');w.receive(M,1)
    with pytest.raises(ValueError):w.receive(M|{'status':'late'},2)
