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


def decode(image: np.ndarray, enhanced: bool = False) -> list[Detection]:
    """Фиксированный набор преобразований, без доступа к эталонным ответам.

    Усиленный режим пробует CLAHE и увеличение только после исходного кадра.
    Результаты объединяются по формату и исходным байтам. Это множество
    значений, а не счётчик физических наклеек с одинаковым содержимым.
    """
    if image is None or image.size == 0:
        raise ValueError("Передано пустое изображение")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("Нужен кадр uint8: оттенки серого или BGR")
    variants = [(gray, 1.)]
    if enhanced:
        variants += [(cv2.createCLAHE(clipLimit=2., tileGridSize=(8, 8)).apply(gray), 1.),
                     (cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), 2.)]
    result = {}
    for frame, scale in variants:
        for b in zxingcpp.read_barcodes(frame, try_rotate=True, try_downscale=True,
                                       try_invert=True, return_errors=False):
            p = b.position
            polygon = tuple((v.x/scale, v.y/scale) for v in
                            (p.top_left, p.top_right, p.bottom_right, p.bottom_left))
            d = Detection(str(b.format), b.text, bytes(b.bytes).hex(), polygon)
            result.setdefault(d.key, d)
    return list(result.values())


def strips(image: np.ndarray, rows: int = 2048, overlap: int = 1024):
    """Полосы линейной камеры с перекрытием; смещение строк возвращается явно."""
    if rows <= 0 or not 0 <= overlap < rows:
        raise ValueError("Требуется rows > overlap >= 0")
    start = 0
    while start < image.shape[0]:
        yield start, image[start:start+rows]
        if start+rows >= image.shape[0]:
            break
        start += rows-overlap


def decode_strips(image: np.ndarray, rows=2048, overlap=1024):
    found = {}
    for offset, strip in strips(image, rows, overlap):
        for d in decode(strip):
            mapped = Detection(d.format, d.text, d.payload_hex,
                               tuple((x, y+offset) for x, y in d.polygon))
            found.setdefault(mapped.key, mapped)
    return list(found.values())
