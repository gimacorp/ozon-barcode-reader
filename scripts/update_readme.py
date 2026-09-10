"""Обновить таблицу README из тех же входов, что используются в PDF."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from barcode_reader.materials import load_materials


def run() -> None:
    bundle, _ = load_materials(ROOT)
    n = bundle["nominal"]
    load = bundle["load_replay"]
    a = next(
        r
        for r in bundle["ablation"]["summary"]
        if (r["mode"], r["policy"], r["level"]) == ("code128_45", "one", "all")
    )
    fmt = lambda x: f"{x:.1f}".replace(".", ",")
    table = f"""| Проверка | Результат |
|---|---|
| Физическая модель, четыре этикетки на грань | {n["exact_boxes"]}/{n["boxes"]} полных множеств; {n["unique_values_found"]}/{n["labels"]} истинных значений; {sum(r["fp"] for r in n["rows"])} ложных |
| Стресс-набор, Code 128 +45° | {a["exact"]}/{a["boxes"]} полных множеств; {a["tp"]}/{a["tp"] + a["fn"]} значений; {a["fp"]} ложных |
| CPU replay, {load["runs"]} отдельных запуска | {load["boxes"]} коробок / {len(load["measurements"])} заданий; {load["exact_boxes"]}/{load["boxes"]} полных множеств |
| Время CPU replay | p95 {fmt(load["p95_ms"])} мс; p99 {fmt(load["p99_ms"])} мс; просрочек {sum(r["late"] for r in load["outcomes"])}/{load["boxes"]} |
| Измерительная машина | {load["metadata"]["cpu"]}; {load["workers"]} рабочих процессов; подготовка массивов включена |
"""
    path = ROOT / "README.md"
    text = path.read_text()
    start = text.index("<!-- RESULTS:START -->") + len("<!-- RESULTS:START -->")
    end = text.index("<!-- RESULTS:END -->")
    path.write_text(text[:start] + "\n" + table + text[end:])


if __name__ == "__main__":
    run()
