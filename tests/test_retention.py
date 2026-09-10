import numpy as np

from barcode_reader.assignment import FaceRegion
from barcode_reader.control import FACES, BoxTracker
from barcode_reader.coverage import CaptureContract
from barcode_reader.pipeline import Pipeline
from barcode_reader.session import Session


def test_long_stream_releases_closed_tracks_and_assignments():
    t = BoxTracker(Session("stream", "os"))
    p = Pipeline(t)
    peak = 0
    for i in range(5000):
        name = str(i)
        now = i * 2
        t.register(
            name,
            now,
            now + 1,
            now + 1.5,
            contract=CaptureContract.image_demo({f: "f" for f in FACES}),
        )
        p.assigner.assign(
            "top",
            name,
            "roi",
            [(1, 1), (2, 1), (2, 2), (1, 2)],
            np.eye(3),
            [FaceRegion(name, "top", (0, 0, 3, 3))],
        )
        t.finalize(name, now + 1)
        p.prune(now + 1)
        peak = max(peak, len(t.boxes))
        assert len(p.assigner.assigned) == len(t.boxes)
    assert peak <= 4
    p.prune(10010)
    assert not t.boxes and not p.assigner.assigned
