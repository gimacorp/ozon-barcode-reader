"""Приближённая некогерентная MTF и изображение: дифракция, дефокус, смаз."""

import math

import numpy as np


def diffraction_mtf(frequency_lp_mm, aperture, wavelength_mm=0.00055):
    q = np.clip(np.asarray(frequency_lp_mm) * aperture * wavelength_mm, 0, 1)
    return 2 / np.pi * (np.arccos(q) - q * np.sqrt(1 - q * q))


def disk_mtf(frequency_lp_mm, diameter_mm):
    # 2 J1(x)/x; сходящийся ряд для используемого диапазона x < 6.
    x = np.asarray(frequency_lp_mm) * np.pi * diameter_mm
    term = np.ones_like(x, dtype=float)
    out = term.copy()
    for k in range(1, 40):
        term *= -(x * x / 4) / (k * (k + 1))
        out += term
    return out


def contrast(
    module_px=3.73,
    pixel_mm=0.0032,
    aperture=11.0,
    coc_px=2.0,
    motion_px=0.5,
    aberration_sigma_px=0.35,
):
    f = 1 / (2 * module_px * pixel_mm)
    terms = {
        "diffraction": float(diffraction_mtf(f, aperture)),
        "defocus": float(abs(disk_mtf(f, coc_px * pixel_mm))),
        "motion": float(abs(np.sinc(f * motion_px * pixel_mm))),
        "pixel": float(abs(np.sinc(f * pixel_mm))),
        "aberration_assumption": float(
            np.exp(-2 * np.pi**2 * (aberration_sigma_px * pixel_mm * f) ** 2)
        ),
    }
    return {
        "frequency_lp_mm": f,
        "terms": terms,
        "mtf_product": math.prod(terms.values()),
    }


def defocus_diameter(focal, aperture, focus, distance, pixel_mm):
    v0 = focal * focus / (focus - focal)
    v = focal * np.asarray(distance) / (np.asarray(distance) - focal)
    return np.abs(v0 - v) / v * focal / aperture / pixel_mm


def degrade(gray, pixel_mm, aperture, coc_px, motion_px=0.0, aberration_sigma_px=0.35):
    """Стационарный OTF для одного малого участка, FFT с белым полем вокруг.

    Диаметр дефокуса задаётся худшим углом участка. Аберрации представлены
    отдельным предположением Gaussian sigma=0,35 px; паспортная MTF объектива
    на рабочем расстоянии требует измерения. Знак OTF диска сохраняется.
    """
    pad = 32
    src = np.pad(gray.astype(float), pad, constant_values=255)
    h, w = src.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    r = np.sqrt(fx * fx + fy * fy)
    otf = diffraction_mtf(r / pixel_mm, aperture)
    # Численное ядро диска: устойчиво при большом дефокусе.
    if coc_px > 0.1:
        n = max(3, int(np.ceil(coc_px)) + 2)
        n += 1 - n % 2
        axis = (np.arange(n * 8) + 0.5) / 8 - n / 2
        yy, xx = np.meshgrid(axis, axis)
        kernel = (
            ((xx * xx + yy * yy) <= (coc_px / 2) ** 2)
            .astype(float)
            .reshape(n, 8, n, 8)
            .mean((1, 3))
        )
        if kernel.sum() == 0:
            kernel[n // 2, n // 2] = 1
        kernel /= kernel.sum()
        impulse = np.zeros_like(src)
        cy, cx = h // 2, w // 2
        impulse[cy - n // 2 : cy + n // 2 + 1, cx - n // 2 : cx + n // 2 + 1] = kernel
        otf *= np.fft.rfft2(np.fft.ifftshift(impulse)).real
    otf *= np.sinc(fx * motion_px) * np.sinc(fx) * np.sinc(fy)
    otf *= np.exp(-2 * np.pi**2 * aberration_sigma_px**2 * r * r)
    result = np.fft.irfft2(np.fft.rfft2(src) * otf, s=src.shape)
    return np.clip(result[pad:-pad, pad:-pad], 0, 255).astype(np.uint8)
