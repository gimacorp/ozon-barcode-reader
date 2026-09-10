import numpy as np

from barcode_reader.decoder import decode_strips
from barcode_reader.optics import contrast, degrade, diffraction_mtf
from barcode_reader.synthetic import label


def test_small_defocus_remains_finite_white():
    image = np.full((64, 80), 255, np.uint8)
    assert np.min(degrade(image, 0.0032, 11, 0.12)) >= 254


def test_mtf_at_zero_and_cutoff():
    assert diffraction_mtf(0, 11) == 1
    assert diffraction_mtf(1 / (11 * 0.00055), 11) == 0
    assert 0.5 < contrast()["mtf_product"] < 0.65


def test_start_and_end_labels_read_in_single_edge_strip():
    a = label("START001", 3.86)
    b = label("FINAL001", 3.86)
    image = np.full((2500, 1500), 255, np.uint8)
    image[: a.shape[0], 100 : 100 + a.shape[1]] = a
    image[-b.shape[0] :, 100 : 100 + b.shape[1]] = b
    assert {d.text for d in decode_strips(image, rows=1024, overlap=512)} == {
        "START001",
        "FINAL001",
    }
