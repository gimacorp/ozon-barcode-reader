"""Граничные условия оптики, временного бюджета и согласованности конфигурации."""

import math
import pytest
from barcode_reader.engineering import (
    pixels_per_module, motion_blur_px, deadline_budget, depth_of_field,
    zero_failures_upper_bound, summarize, load_config, working_distance,
)
from barcode_reader.geometry import evaluate_end_face


def test_sampling_uses_module_not_label():
    assert pixels_per_module(8192,700,.33)==pytest.approx(3.861942857)
    assert pixels_per_module(8192,700,.33,60)==pytest.approx(1.9309714285)


@pytest.mark.parametrize("fov,module,angle",[(0,.33,0),(700,0,0),(700,.33,90)])
def test_invalid_optics_rejected(fov,module,angle):
    with pytest.raises(ValueError):
        pixels_per_module(8192,fov,module,angle)


def test_motion_blur_unit_conversion():
    assert motion_blur_px(1000,40,1/12)==pytest.approx(.48)


def test_deadline_measures_front_of_box():
    assert deadline_budget(3000,1400,600,1000,.1,.25)==pytest.approx(.65)
    assert deadline_budget(2000,1400,600,1000,.1,.25)<0


def test_dof_contains_focus():
    near,far=depth_of_field(50,8,.0064,1300)
    assert near<1300<far
    assert far-near>60


def test_required_evidence_is_not_100_trials():
    assert zero_failures_upper_bound(100)==pytest.approx(.02951305)
    assert zero_failures_upper_bound(2995)<.001


def test_nominal_config_consistent():
    c=load_config();s=summarize(c)
    assert s["budget_slack_s"]>0
    assert c["line_exposure_us"]<s["line_exposure_period_us"]
    assert s["overlap_covers_label"]
    assert s["line_px_module_motion"]>=c["sampling_target_px"]
    assert s["encoder_step_mm"]==pytest.approx(s["line_step_mm"])
    assert s["area_rate_one_MB_s"]<1250 # Только физический предел 10 Gb/s.


def test_end_face_sampling_and_focus_sweep():
    g=evaluate_end_face(load_config())
    assert g["min_covered_fraction"]==1.0
    assert g["min_best_px_per_module"]>=3


def test_fov_lens_roundtrip():
    assert working_distance(28,28.672,700)==pytest.approx(711.59375)
def test_whole_label_focus_requires_more_than_point_coverage():
    from barcode_reader.geometry import evaluate_label_focus
    c = load_config()
    assert evaluate_label_focus(c)["min_whole_label_coverage"] == 1
    assert evaluate_label_focus(c, 8)["min_whole_label_coverage"] < 1


def test_speed_changes_last_observation_and_deadline():
    c=load_config();base=summarize(c)
    fast=summarize(c|{"speed_mm_s":2000})
    assert base["last_rear_observation_x_mm"]==1415
    assert fast["last_rear_observation_x_mm"]==1570
    assert fast["remaining_processing_delivery_s"]==pytest.approx(.065)


@pytest.mark.parametrize("bad",[float("nan"),float("inf"),-1])
def test_nonfinite_blur_rejected(bad):
    with pytest.raises(ValueError):motion_blur_px(bad,40,.08)
    with pytest.raises(ValueError):motion_blur_px(1000,bad,.08)
