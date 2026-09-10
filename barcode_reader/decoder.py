"""Чтение всех кодов в полном кадре; координаты всегда в исходном изображении."""

from dataclasses import dataclass

import cv2
import numpy as np
import zxingcpp


@dataclass(frozen=True)
class Detection:
    format: str
    text: str
    payload_hex: str
    polygon: tuple[tuple[float, float], ...]

    @property
    def key(self):
        return self.format, self.payload_hex


def _views(gray: np.ndarray, enhanced: bool, try_diagonal: bool):
    """Дополнительные 45° покрывают диагональные коды; матрица ведёт в исходный кадр."""
    height, width = gray.shape
    for angle in (0, 45) if try_diagonal else (0,):
        transform = np.eye(3, dtype=np.float64)
        frame = gray
        if angle:
            affine = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
            cosine, sine = abs(affine[0, 0]), abs(affine[0, 1])
            nw, nh = (
                int(np.ceil(width * cosine + height * sine)),
                int(np.ceil(height * cosine + width * sine)),
            )
            affine[0, 2] += nw / 2 - width / 2
            affine[1, 2] += nh / 2 - height / 2
            transform[:2] = affine
            frame = cv2.warpAffine(
                gray, affine, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=255
            )
        inverse = np.linalg.inv(transform)
        yield frame, inverse
        if enhanced:
            yield (
                cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(frame),
                inverse,
            )
            yield (
                cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
                inverse @ np.diag([0.5, 0.5, 1.0]),
            )


def parse_formats(spec: str | None):
    """Явный перечень символик; None сохраняет режим сравнения со всеми форматами."""
    if spec is None:
        return None
    result = []
    for name in spec.split(","):
        value = getattr(zxingcpp.BarcodeFormat, name.strip(), None)
        if value is None or not isinstance(value, zxingcpp.BarcodeFormat):
            raise ValueError(f"Неизвестная символика: {name}")
        if value != zxingcpp.BarcodeFormat.NONE:
            result.append(value)
    if not result:
        raise ValueError("Укажите хотя бы одну символику")
    return zxingcpp.BarcodeFormats(result)


def decode(
    image: np.ndarray,
    enhanced: bool = False,
    *,
    try_diagonal: bool = True,
    formats: str | None = "Code128",
) -> list[Detection]:
    """Фиксированный набор преобразований, без доступа к эталонным ответам.

    Исходный кадр и его поворот на 45° проверяются всегда. Усиленный режим
    дополнительно пробует CLAHE и увеличение. try_diagonal=False воспроизводит
    исходный базовый вариант для сравнительного эксперимента.
    По умолчанию включён Code128, как в демонстрационной выборке. Дополнительные
    символики перечисляются явно: например, formats="Code128,DataMatrix".
    Возвращает пространственные обнаружения. Повторные виды одной области
    объединяются; одинаковые значения в разных областях сохраняются до назначения
    коробке. BoxTracker объединяет значения внутри назначенной коробки.
    """
    if image is None or image.size == 0:
        raise ValueError("Передано пустое изображение")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("Нужен кадр uint8: оттенки серого или BGR")
    result = []
    parsed = parse_formats(formats)
    allowed = {} if parsed is None else {"formats": parsed}
    for frame, inverse in _views(gray, enhanced, try_diagonal):
        for b in zxingcpp.read_barcodes(
            frame,
            **allowed,
            try_rotate=True,
            try_downscale=True,
            try_invert=True,
            return_errors=False,
        ):
            p = b.position
            points = (
                np.array(
                    [
                        [v.x, v.y, 1.0]
                        for v in (
                            p.top_left,
                            p.top_right,
                            p.bottom_right,
                            p.bottom_left,
                        )
                    ]
                )
                @ inverse.T
            )
            polygon = tuple((float(x), float(y)) for x, y, _ in points)
            d = Detection(str(b.format), b.text, bytes(b.bytes).hex(), polygon)
            append_spatial(result, d)
    return result


def append_spatial(result: list[Detection], candidate: Detection) -> None:
    """Удаляет повторы одного участка между преобразованиями изображения."""
    p = np.asarray(candidate.polygon, np.float32)
    area = abs(cv2.contourArea(p))
    for old in result:
        if old.key != candidate.key:
            continue
        q = np.asarray(old.polygon, np.float32)
        other_area = abs(cv2.contourArea(q))
        if min(area, other_area) > 0:
            intersection, _ = cv2.intersectConvexConvex(
                cv2.convexHull(p), cv2.convexHull(q)
            )
            if intersection / min(area, other_area) > 0.5:
                return
        elif np.linalg.norm(p.mean(0) - q.mean(0)) < 3:
            return
    result.append(candidate)


def strips(image: np.ndarray, rows: int = 2048, overlap: int = 1024):
    """Полосы линейной камеры с перекрытием; смещение строк возвращается явно."""
    if rows <= 0 or not 0 <= overlap < rows:
        raise ValueError("Требуется rows > overlap >= 0")
    start = 0
    while start < image.shape[0]:
        yield start, image[start : start + rows]
        if start + rows >= image.shape[0]:
            break
        start += rows - overlap


def decode_strips(
    image: np.ndarray,
    rows=2048,
    overlap=1024,
    *,
    formats="Code128",
    enhanced=False,
    try_diagonal=True,
):
    found = []
    for offset, strip in strips(image, rows, overlap):
        for d in decode(strip, enhanced, formats=formats, try_diagonal=try_diagonal):
            mapped = Detection(
                d.format,
                d.text,
                d.payload_hex,
                tuple((x, y + offset) for x, y in d.polygon),
            )
            append_spatial(found, mapped)
    return found
