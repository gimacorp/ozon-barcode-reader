import numpy as np
import pytest
import zxingcpp

from barcode_reader.assignment import Assigner, FaceRegion
from barcode_reader.control import FACES, BoxTracker
from barcode_reader.coverage import CaptureContract, Evidence, independent_count
from barcode_reader.decoder import decode, decode_strips
from barcode_reader.metrics import score, value_key


def test_capture_requires_every_frame_and_every_row():
    c = CaptureContract.production("B", session_id="S")
    for f in ("front", "rear"):
        for i in range(5):
            c.record(f, Evidence(f, f"B-{f}-{i}", session_id="S", box_id="B"))
    for f in ("top", "bottom", "left", "right"):
        for span in c.required_chunks[f]:
            c.record(f, Evidence(f, f"B-{f}-scan", span, "S", "B"), [300])
    assert c.complete_faces() == {"front", "rear"}
    for f in ("top", "bottom", "left", "right"):
        c.record(f, Evidence(f, f"B-{f}-scan", (0, 2048), "S", "B"))
    assert c.complete_faces() == FACES


@pytest.mark.parametrize(
    "field,value",
    [
        ("camera", "foreign"),
        ("acquisition", "other-scan"),
        ("session_id", "old"),
        ("box_id", "other"),
    ],
)
def test_coverage_rejects_foreign_source(field, value):
    from dataclasses import replace

    c = CaptureContract.production("B", session_id="S")
    good = Evidence("top", "B-top-scan", (0, 2048), "S", "B")
    assert not c.record("top", replace(good, **{field: value}))
    assert not c.processed_rows
    area = Evidence("front", "B-front-0", session_id="S", box_id="B")
    assert not c.record("front", replace(area, **{field: value}))


def test_production_single_frame_is_incomplete():
    t = BoxTracker()
    t.register("B", 0, 2, 3)
    for f in FACES:
        t.observe("B", f, "one", 1, 1.1, [])
    assert t.finalize("B", 2)["status"] == "incomplete_views"


def test_strip_overlap_is_one_confirmation():
    assert (
        independent_count(
            [Evidence("top", "scan", (0, 2048)), Evidence("top", "scan", (1024, 3072))]
        )
        == 1
    )
    assert independent_count([Evidence("front", "f1"), Evidence("front", "f2")]) == 2


def test_assignment_overlapping_windows_multiple_rois_and_reuse():
    a = Assigner()
    regions = [
        FaceRegion("A", "top", (0, 0, 100, 100)),
        FaceRegion("B", "top", (100, 0, 200, 100)),
    ]
    p = np.array([[10, 10], [20, 10], [20, 20], [10, 20]])
    assert a.assign("c", "same-frame", "roi-1", p, np.eye(3), regions) == ("A", "top")
    assert a.assign("c", "same-frame", "roi-2", p + [100, 0], np.eye(3), regions) == (
        "B",
        "top",
    )
    assert (
        a.assign("c", "same-frame", "roi-1", p + [100, 0], np.eye(3), regions) is None
    )
    assert (
        a.assign(
            "c",
            "other",
            "roi",
            p,
            np.eye(3),
            regions + [FaceRegion("C", "top", (0, 0, 50, 50))],
        )
        is None
    )
    assert a.assign("c", "other", "boundary", p + [85, 0], np.eye(3), regions) is None


def test_format_bytes_and_duplicate_label_values():
    binary = ("Data Matrix", b"\x00\xff".hex())
    same_text = ("Code 128", b"12".hex())
    other = ("Data Matrix", b"12".hex())
    assert score([same_text, other, binary, binary], [same_text, binary]) == {
        "expected": 3,
        "tp": 2,
        "fp": 0,
        "fn": 1,
        "exact": 0,
    }
    assert value_key({"format": "Data Matrix", "payload_hex": "00FF"}) == binary


def test_actual_data_matrix_through_strips():
    barcode = zxingcpp.create_barcode(b"\x00\xffDM", zxingcpp.BarcodeFormat.DataMatrix)
    img = np.asarray(
        zxingcpp.write_barcode_to_image(barcode, scale=5, add_quiet_zones=True)
    )
    canvas = np.full((600, 600), 255, np.uint8)
    h, w = img.shape
    canvas[250 : 250 + h, 250 : 250 + w] = img
    a = decode_strips(canvas, rows=400, overlap=300, formats="DataMatrix")
    assert len(a) == 1 and a[0].payload_hex == b"\x00\xffDM".hex()
    assert not decode_strips(canvas, rows=400, overlap=300, formats="Code128")


def test_geometric_assignment_to_tracker_rejects_reused_roi():
    from barcode_reader.assignment import observe_assigned
    from barcode_reader.decoder import Detection

    a = Assigner()
    t = BoxTracker()
    for name in ("A", "B"):
        t.register(name, 0, 2, 3, contract=CaptureContract.image_demo({"top": "same"}))
    regions = [
        FaceRegion("A", "top", (0, 0, 100, 100)),
        FaceRegion("B", "top", (100, 0, 200, 100)),
    ]
    polygon = ((10, 10), (20, 10), (20, 20), (10, 20))
    d = Detection("Code 128", "12", "3132", polygon)
    kw = dict(
        camera="top",
        frame_id="same",
        roi_id="r1",
        image_to_face=np.eye(3),
        regions=regions,
        captured_s=1,
        completed_s=1.1,
    )
    assert observe_assigned(a, t, detection=d, **kw)
    moved = Detection(
        d.format, d.text, d.payload_hex, tuple((x + 100, y) for x, y in polygon)
    )
    assert not observe_assigned(a, t, detection=moved, **kw)
    assert not t.boxes["B"].observations


def test_two_physical_identical_labels_preserve_spatial_instances():
    from barcode_reader.synthetic import label

    stamp = label("REPEAT01", 3.86)
    h, w = stamp.shape
    image = np.full((800, 1800), 255, np.uint8)
    for x in (100, 1000):
        image[200 : 200 + h, x : x + w] = stamp
    found = decode(image)
    assert len(found) == 2 and {d.text for d in found} == {"REPEAT01"}


def test_actual_same_text_in_two_symbologies_remains_two_values():
    from barcode_reader.synthetic import label

    linear = label("SAME123", 3.86)
    matrix = np.asarray(
        zxingcpp.write_barcode_to_image(
            zxingcpp.create_barcode("SAME123", zxingcpp.BarcodeFormat.DataMatrix),
            scale=8,
            add_quiet_zones=True,
        )
    )
    image = np.full((800, 1600), 255, np.uint8)
    for x, stamp in [(100, linear), (1000, matrix)]:
        h, w = stamp.shape
        image[200 : 200 + h, x : x + w] = stamp
    ds = decode(image, formats="Code128,DataMatrix")
    assert len(ds) == 2 and len({d.format for d in ds}) == 2
    assert {d.payload_hex for d in ds} == {b"SAME123".hex()}
