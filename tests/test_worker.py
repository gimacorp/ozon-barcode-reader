import cv2
import pytest
from barcode_reader.synthetic import label
from barcode_reader.worker import decode_file_bounded


def test_worker_reads_real_file(tmp_path):
    path=tmp_path/"code.png"
    cv2.imwrite(str(path),label("WORKER0001"))
    assert decode_file_bounded(path,5)[0]["text"]=="WORKER0001"


def test_worker_deadline_covers_process_start(tmp_path):
    path=tmp_path/"code.png";cv2.imwrite(str(path),label("WORKER0001"))
    with pytest.raises(TimeoutError):decode_file_bounded(path,.000001)


def test_worker_reports_invalid_input(tmp_path):
    with pytest.raises(ValueError):decode_file_bounded(tmp_path/"missing.png",5)
    with pytest.raises(ValueError):decode_file_bounded("x",-1)
