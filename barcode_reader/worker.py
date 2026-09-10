"""Изолированное декодирование файла с ограничением общего времени процесса."""

import json
import math
import subprocess
import sys


def decode_file_bounded(path, timeout_s=5.0, *, enhanced=False, formats="Code128"):
    """При превышении времени ОС завершает дочерний процесс вместе с C++ вызовом.

    Время включает старт Python, импорты, чтение файла и декодирование.
    Промышленная версия использует заранее запущенные процессы и общий буфер.
    """
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("Срок должен быть конечным положительным числом")
    command = [
        sys.executable,
        "-m",
        "barcode_reader.worker",
        str(path),
        formats,
        "1" if enhanced else "0",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(f"Превышен срок декодирования {timeout_s:g} с") from error
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Ошибка процесса декодирования")
    return json.loads(result.stdout)


def main():
    from dataclasses import asdict

    import cv2

    from .decoder import decode

    try:
        path, formats, enhanced = sys.argv[1:]
        image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Не удалось открыть изображение")
        result = [asdict(d) for d in decode(image, enhanced == "1", formats=formats)]
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
