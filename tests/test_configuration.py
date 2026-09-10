import math

from barcode_reader.coverage import row_spans
from barcode_reader.engineering import load_config, summarize
from barcode_reader.scheduling import arrivals


def test_two_speeds_propagate_to_geometry_schedule_and_strip_contract():
    original = load_config()
    for speed in (1000, 1500):
        c = original | {"speed_mm_s": speed}
        result = summarize(c)
        jobs = arrivals(2, config=c)
        rows = math.ceil(c["box_length_mm"] * c["line_rate_hz"] / speed)
        planned = row_spans(rows, c["line_strip_rows"], c["line_strip_overlap_rows"])
        top = [j for j in jobs if j.box == 0 and j.channel == "top"]
        assert tuple(j.rows for j in top) == planned
        assert (
            top[-1].captured_s
            == c["line_positions_mm"]["top"] / speed + rows / c["line_rate_hz"]
        )
        last = max(j.captured_s for j in jobs if j.box == 0)
        budget = jobs[0].deadline - last
        # Инженерный бюджет округляет позицию последнего торца консервативно.
        assert (
            0
            <= budget - result["remaining_processing_delivery_s"]
            < c["observation_position_rounding_mm"] / speed
        )
        assert (
            jobs[0].deadline
            == c["sorter_x_mm"] / speed - c["plc_actuation_s"] - c["guard_s"]
        )
