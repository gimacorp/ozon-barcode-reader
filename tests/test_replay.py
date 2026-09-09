from barcode_reader.replay import run_replay


def test_six_faces_multiple_codes_and_two_boxes():
    result=run_replay()
    assert len(result["commands"])==2
    for b in result["boxes"]:
        assert b["exact_set"]
        assert len(b["message"]["codes"])==12
        assert len(b["message"]["observed_faces"])==6
        assert b["message"]["status"]=="read"
        assert b["retry_ack"]["ack"]=="duplicate"
    assert set(result["boxes"][0]["expected"]).isdisjoint(result["boxes"][1]["expected"])
