"""Воспроизводимые расчёты. Длины в мм, время в секундах, потоки в байтах/с."""

from __future__ import annotations

import json
import math
from pathlib import Path


def positive(value: float, name: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: требуется конечное положительное число")
    return value


def pixels_per_module(pixels: int, fov_mm: float, module_mm: float,
                      angle_deg: float = 0.0) -> float:
    """Приближённая локальная дискретизация, без модели фокуса и MTF."""
    positive(pixels, "pixels")
    positive(fov_mm, "fov_mm")
    positive(module_mm, "module_mm")
    if not math.isfinite(angle_deg) or abs(angle_deg) >= 90:
        raise ValueError("Угол должен быть строго между -90 и 90 градусами")
    return pixels / fov_mm * module_mm * math.cos(math.radians(angle_deg))


def motion_blur_px(speed_mm_s: float, exposure_us: float,
                   mm_per_pixel: float) -> float:
    positive(mm_per_pixel, "mm_per_pixel")
    if not all(math.isfinite(v) and v >= 0 for v in (speed_mm_s, exposure_us)):
        raise ValueError("Скорость и выдержка должны быть конечными и неотрицательными")
    return speed_mm_s * exposure_us * 1e-6 / mm_per_pixel


def required_line_rate(speed_mm_s: float, step_mm: float) -> float:
    positive(speed_mm_s, "speed_mm_s")
    return speed_mm_s / positive(step_mm, "step_mm")


def working_distance(focal_mm: float, sensor_mm: float, fov_mm: float) -> float:
    """Тонкая линза: расстояние от главной плоскости, не передней оправы."""
    return positive(focal_mm, "focal_mm") * (
        1 + positive(fov_mm, "fov_mm") / positive(sensor_mm, "sensor_mm"))


def depth_of_field(focal_mm: float, aperture: float,
                   coc_mm: float, focus_mm: float) -> tuple[float, float]:
    """Геометрические ближняя/дальняя границы; дифракция сюда не входит."""
    for n, v in [("focal_mm", focal_mm), ("aperture", aperture),
                 ("coc_mm", coc_mm), ("focus_mm", focus_mm)]:
        positive(v, n)
    if focus_mm <= focal_mm:
        raise ValueError("Предмет должен находиться дальше фокусного расстояния")
    hyperfocal = focal_mm * focal_mm / (aperture * coc_mm) + focal_mm
    near = hyperfocal * focus_mm / (hyperfocal + focus_mm - focal_mm)
    denominator = hyperfocal - (focus_mm - focal_mm)
    far = math.inf if denominator <= 0 else hyperfocal * focus_mm / denominator
    return near, far


def deadline_budget(sorter_x_mm: float, last_rear_x_mm: float,
                    box_length_mm: float, speed_mm_s: float,
                    plc_s: float, guard_s: float) -> float:
    """Остаток после последнего наблюдения задней грани до крайней доставки."""
    positive(speed_mm_s, "speed_mm_s")
    if min(plc_s, guard_s, box_length_mm) < 0:
        raise ValueError("Резервы времени и длина не могут быть отрицательными")
    return (sorter_x_mm - last_rear_x_mm - box_length_mm) / speed_mm_s - plc_s - guard_s


def zero_failures_upper_bound(trials: int, confidence: float = 0.95) -> float:
    """Односторонняя точная биномиальная граница при нуле отказов."""
    if trials < 1 or not 0 < confidence < 1:
        raise ValueError("Нужны n >= 1 и 0 < confidence < 1")
    return 1 - (1 - confidence) ** (1 / trials)


def summarize(config: dict) -> dict:
    c = config
    v = positive(c["speed_mm_s"], "speed_mm_s")
    line_step = v / positive(c["line_rate_hz"], "line_rate_hz")
    transverse_step = c["line_fov_horizontal_mm"] / c["line_pixels"]
    area_step = c["area_fov_width_mm"] / c["area_pixels_x"]
    sensor_area = c["area_pixels_x"] * c["area_sensor_pixel_um"] / 1000
    area_wd = working_distance(c["area_focal_length_mm"], sensor_area,
                               c["area_fov_width_mm"])
    elevation = c["area_elevation_mm"]
    if elevation >= area_wd:
        raise ValueError("Высота камеры превышает рабочее расстояние")
    angle = math.degrees(math.asin(elevation / area_wd))
    near, far = depth_of_field(c["area_focal_length_mm"], c["area_aperture"],
        c["area_focus_coc_px"] * c["area_sensor_pixel_um"] / 1000, area_wd)
    bytes_px = c["bits_per_pixel"] / 8
    area_frame = c["area_pixels_x"] * c["area_pixels_y"] * bytes_px
    line_rate_bytes = c["line_pixels"] * c["line_rate_hz"] * bytes_px
    lines_per_box = math.ceil(c["box_length_mm"] / line_step)
    per_box = (c["line_camera_count"] * c["line_pixels"] * lines_per_box * bytes_px
               + c["area_camera_count"] * c["area_frames_per_box"] * area_frame)
    # Крайний кадр учитывает полшага неопределённости фазы запуска серии.
    camera_dx = math.sqrt(area_wd**2-elevation**2)
    last_rear = c["rear_camera_x_mm"] + camera_dx + c["area_frames_per_box"]/2*v/c["area_frame_rate_hz"]
    rounding = positive(c["observation_position_rounding_mm"], "observation_position_rounding_mm")
    last_rear = math.ceil(last_rear/rounding)*rounding
    remaining = deadline_budget(c["sorter_x_mm"], last_rear,
        c["box_length_mm"], v, c["plc_actuation_s"], c["guard_s"])
    label_diagonal = math.hypot(c["max_label_width_mm"], c["max_label_height_mm"])
    return {
        "assumptions": "Геометрические расчёты; MTF и производственная точность не измерены",
        "throughput_boxes_h": 3600 / c["leading_edge_interval_s"],
        "line_step_mm": line_step,
        "horizontal_step_mm": transverse_step,
        "line_px_module_horizontal": c["min_module_mm"] / transverse_step,
        "line_px_module_motion": c["min_module_mm"] / line_step,
        "line_px_module_vertical": pixels_per_module(c["line_pixels"],
            c["line_fov_vertical_mm"], c["min_module_mm"]),
        "line_exposure_period_us": 1e6 / c["line_rate_hz"],
        "line_blur_px": motion_blur_px(v, c["line_exposure_us"], line_step),
        "line_rate_equal_pixels_hz": required_line_rate(v, transverse_step),
        "area_mm_px": area_step,
        "area_angle_deg": angle,
        "area_wd_mm": area_wd,
        "area_horizontal_distance_mm": math.sqrt(area_wd**2-elevation**2),
        "area_px_module_center": pixels_per_module(c["area_pixels_x"],
            c["area_fov_width_mm"], c["min_module_mm"], angle),
        "area_blur_conservative_px": motion_blur_px(v, c["area_exposure_us"], area_step),
        "area_focus_near_mm": near,
        "area_focus_far_mm": far,
        "area_dof_mm": far-near,
        "area_frame_movement_mm": v/c["area_frame_rate_hz"],
        "diffraction_airy_diameter_px_550nm": 2.44*0.00055*c["area_aperture"] /
            (c["area_sensor_pixel_um"]/1000),
        "line_working_distance_horizontal_mm": working_distance(c["line_focal_length_mm"],
            c["line_pixels"]*c["line_sensor_pixel_um"]/1000, c["line_fov_horizontal_mm"]),
        "line_working_distance_vertical_mm": working_distance(c["line_focal_length_mm"],
            c["line_pixels"]*c["line_sensor_pixel_um"]/1000, c["line_fov_vertical_mm"]),
        "line_rate_one_MB_s": line_rate_bytes/1e6,
        "line_rate_total_MB_s": c["line_camera_count"]*line_rate_bytes/1e6,
        "area_frame_MB": area_frame/1e6,
        "area_rate_one_MB_s": area_frame*c["area_frame_rate_hz"]/1e6,
        "peak_total_MB_s": (c["line_camera_count"]*line_rate_bytes +
            c["area_camera_count"]*area_frame*c["area_frame_rate_hz"])/1e6,
        "per_box_MB": per_box/1e6,
        "average_MB_s": per_box/c["leading_edge_interval_s"]/1e6,
        "remaining_processing_delivery_s": remaining,
        "last_rear_observation_x_mm": last_rear,
        "budget_slack_s": remaining-c["processing_budget_s"]-c["delivery_budget_s"],
        "encoder_step_mm": c["encoder_wheel_circumference_mm"]/c["encoder_pulses_per_rev"],
        "strip_height_mm": c["line_strip_rows"]*line_step,
        "strip_overlap_mm": c["line_strip_overlap_rows"]*line_step,
        "max_label_diagonal_mm": label_diagonal,
        "overlap_covers_label": c["line_strip_overlap_rows"]*line_step >= label_diagonal,
        "zero_errors_n100_upper95": zero_failures_upper_bound(100),
        "trials_for_999_with_zero_failures": math.ceil(math.log(.05)/math.log(.999)),
    }


def load_config(path: str | Path = "configs/conveyor.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_calculations(config_path: str | Path, output: str | Path) -> dict:
    result = summarize(load_config(config_path))
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return result
