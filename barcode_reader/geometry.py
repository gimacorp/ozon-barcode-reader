"""Проекция торцевой плоскости: поле зрения, локальный масштаб и окно фокуса."""

from __future__ import annotations

import math
import numpy as np

from .engineering import working_distance, depth_of_field


def camera_basis(position: np.ndarray, target: np.ndarray):
    forward = target-position
    forward = forward/np.linalg.norm(forward)
    right = np.cross(forward, np.array([0., 0., 1.]))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return right, up, forward


def project(points: np.ndarray, position: np.ndarray, target: np.ndarray,
            focal_px: float, width_px: int, height_px: int):
    right, up, forward = camera_basis(position, target)
    local = (points-position) @ np.stack([right, up, forward], axis=1)
    uv = np.column_stack((width_px/2+focal_px*local[:, 0]/local[:, 2],
                          height_px/2-focal_px*local[:, 1]/local[:, 2]))
    return uv, local[:, 2]


def evaluate_end_face(c: dict) -> dict:
    """Сетка точек и фаз запуска, а не доказательство оптической читаемости.

    Торец движется через фокальную плоскость. Для каждой точки ищется хотя бы
    один кадр с допустимым геометрическим кружком нерезкости и полем зрения.
    """
    f = c["area_focal_length_mm"]
    px = c["area_sensor_pixel_um"]/1000
    nx, ny = c["area_pixels_x"], c["area_pixels_y"]
    wd = working_distance(f, nx*px, c["area_fov_width_mm"])
    h = c["area_elevation_mm"]
    distance_x = math.sqrt(wd*wd-h*h)
    position = np.array([-distance_x, 0., c["box_height_mm"]/2+h])
    target = np.array([0., 0., c["box_height_mm"]/2])
    # Эффективное фокусное в модели тонкой линзы на заданной дистанции.
    image_distance = f*wd/(wd-f)
    focal_px = image_distance/px
    near, far = depth_of_field(f,c["area_aperture"],c["area_focus_coc_px"]*px,wd)
    grid = np.array([[0., y, z] for y in np.linspace(-c["box_width_mm"]/2,
        c["box_width_mm"]/2,17) for z in np.linspace(0,c["box_height_mm"],17)])
    motion_step = c["speed_mm_s"]/c["area_frame_rate_hz"]
    coverages, min_scales = [], []
    for phase in np.linspace(-motion_step/2, motion_step/2, 21):
        covered = np.zeros(len(grid), dtype=bool)
        point_best_scale = np.zeros(len(grid))
        count = c["area_frames_per_box"]
        for shift in (np.arange(count)-(count-1)/2)*motion_step + phase:
            points = grid + [shift,0,0]
            uv, depth = project(points,position,target,focal_px,nx,ny)
            u_y,_=project(points+[0,.01,0],position,target,focal_px,nx,ny)
            u_z,_=project(points+[0,0,.01],position,target,focal_px,nx,ny)
            jac = np.stack(((u_y-uv)/.01,(u_z-uv)/.01),axis=2)
            scale = np.linalg.svd(jac,compute_uv=False)[:,-1]
            valid = ((uv[:,0]>=0)&(uv[:,0]<nx)&(uv[:,1]>=0)&(uv[:,1]<ny)
                     &(depth>=near)&(depth<=far))
            covered |= valid
            point_best_scale = np.maximum(point_best_scale,np.where(valid,scale,0))
        coverages.append(float(covered.mean()))
        min_scales.append(float(point_best_scale.min()))
    return {
        "model": "Тонкая линза, плоский торец, номинальное центрирование; сетка и фазы",
        "points_per_phase": len(grid),
        "trigger_phases": len(coverages),
        "frames_per_phase": c["area_frames_per_box"],
        "min_covered_fraction": min(coverages),
        "min_best_px_per_mm": min(min_scales),
        "min_best_px_per_module": min(min_scales)*c["min_module_mm"],
        "focus_center_distance_mm": wd,
        "focus_near_mm": near,
        "focus_far_mm": far,
        "camera_horizontal_offset_mm": distance_x,
        "sweep_span_mm": c["area_frames_per_box"]*motion_step,
        "limitation": "Не моделирует аберрации, дифракцию, блики, изгиб этикетки и проскальзывание",
    }


def evaluate_label_focus(c: dict, aperture: float | None = None) -> dict:
    """Проверка всех углов целой этикетки в одном кадре, включая края торца.

    По 9×9 допустимых центров для каждого из 12 углов; 21 фаза запуска.
    Граница резкости геометрическая, не критерий успешного декодирования.
    """
    f=c["area_focal_length_mm"]; px=c["area_sensor_pixel_um"]/1000
    nx,ny=c["area_pixels_x"],c["area_pixels_y"]
    wd=working_distance(f,nx*px,c["area_fov_width_mm"])
    dx=math.sqrt(wd**2-c["area_elevation_mm"]**2)
    pos=np.array([-dx,0,c["box_height_mm"]/2+c["area_elevation_mm"]])
    target=np.array([0,0,c["box_height_mm"]/2]); fp=f*wd/(wd-f)/px
    ap=aperture if aperture is not None else c["area_aperture"]
    near,far=depth_of_field(f,ap,c["area_focus_coc_px"]*px,wd)
    w,h=c["max_label_width_mm"]/2,c["max_label_height_mm"]/2
    patches=[]
    for angle in np.arange(0,180,15):
        a=np.radians(angle);rot=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
        corners=np.array([[-w,-h],[w,-h],[w,h],[-w,h]])@rot.T
        margins=np.max(np.abs(corners),axis=0)
        for y in np.linspace(-c["box_width_mm"]/2+margins[0],c["box_width_mm"]/2-margins[0],9):
            for z in np.linspace(margins[1],c["box_height_mm"]-margins[1],9):
                patches.append(np.column_stack([np.zeros(4),corners+[y,z]]))
    patches=np.array(patches);step=c["speed_mm_s"]/c["area_frame_rate_hz"]
    worst=1.;count=c["area_frames_per_box"]
    for phase in np.linspace(-step/2,step/2,21):
        covered=np.zeros(len(patches),bool)
        for shift in (np.arange(count)-(count-1)/2)*step+phase:
            uv,d=project((patches+[shift,0,0]).reshape(-1,3),pos,target,fp,nx,ny)
            valid=((d>=near)&(d<=far)&(uv[:,0]>=0)&(uv[:,0]<nx)&(uv[:,1]>=0)&(uv[:,1]<ny)).reshape(-1,4).all(1)
            covered|=valid
        worst=min(worst,float(covered.mean()))
    return {"aperture":ap,"labels_per_phase":len(patches),"phases":21,
            "min_whole_label_coverage":worst,"geometric_dof_mm":far-near,
            "limitation":"Дискретная номинальная геометрия. Не учитывает MTF, дифракцию, вибрацию и кривизну коробки."}
