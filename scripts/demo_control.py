from barcode_reader.coverage import CaptureContract

"""Пример передачи полного пакета и повторного подтверждения имитатором ПЛК."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from barcode_reader.control import FACES, BoxTracker, MockPLC
from barcode_reader.decoder import decode
from barcode_reader.synthetic import label


def demo():
    tracker = BoxTracker()
    tracker.register(
        "DEMO-0001",
        0,
        2,
        2.635,
        contract=CaptureContract.image_demo({f: "frame-1" for f in FACES}),
    )
    readings = decode(label("DEMO000001"))
    for face in sorted(FACES):
        tracker.observe(
            "DEMO-0001", face, "frame-1", 1.5, 1.7, readings if face == "top" else []
        )
    message = tracker.finalize("DEMO-0001", 2.2)
    plc = MockPLC()
    return {
        "message": message,
        "first_ack": plc.receive(message, 2.25),
        "retry_ack": plc.receive(message, 2.3),
        "commands": plc.commands,
    }


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
