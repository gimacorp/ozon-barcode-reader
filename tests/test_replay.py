from barcode_reader.replay import run_replay


def test_image_to_durable_wcs():
    r = run_replay()
    assert all(b["exact_set"] and b["message"]["status"] == "read" for b in r["boxes"])
    assert all(b["retry_ack"]["receipt"] == "duplicate" for b in r["boxes"])
    assert all(c["action"] == "resolve_all_values" for c in r["commands"])
    assert r["stale_session_rejected"] and r["all_captures_accepted"]
    assert r["pruned_boxes"] == 2 and r["retained_assignments"] == 0
    assert r["dispatch"]["cancelled_boxes"] == 0


def test_missing_planned_strip_blocks_read_even_with_overlap():
    r = run_replay(missing_strip=True)
    assert [b["message"]["status"] for b in r["boxes"]] == ["read", "incomplete_views"]
    assert r["commands"][1]["action"] == "exception_only"
