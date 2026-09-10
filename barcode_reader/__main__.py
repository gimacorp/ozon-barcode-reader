"""Командный интерфейс: python -m barcode_reader --help."""

import argparse
import json
from pathlib import Path

from .engineering import load_config, summarize
from .geometry import evaluate_end_face, evaluate_label_focus
from .provenance import metadata


def main():
    p = argparse.ArgumentParser(
        description="Прототип шестистороннего чтения штрихкодов"
    )
    sub = p.add_subparsers(dest="command", required=True)
    calc = sub.add_parser(
        "calculate", help="Пересчитать геометрию и инженерные бюджеты"
    )
    calc.add_argument("--config", default="configs/conveyor.json")
    calc.add_argument("--output", default="results/calculations.json")
    bench = sub.add_parser(
        "benchmark", help="Запустить воспроизводимый синтетический эксперимент"
    )
    bench.add_argument("--boxes", type=int, default=60)
    bench.add_argument("--seed", type=int, default=20260909)
    bench.add_argument("--output", default="results")
    read = sub.add_parser("decode", help="Прочитать все коды на изображении")
    read.add_argument("image")
    read.add_argument("--enhanced", action="store_true")
    read.add_argument(
        "--formats",
        default="Code128",
        help="Символики через запятую: Code128,DataMatrix,QRCode",
    )
    read.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Срок отдельного процесса, включая загрузку файла; по умолчанию 5 с",
    )
    args = p.parse_args()
    if args.command == "calculate":
        c = load_config(args.config)
        result = {
            "metadata": metadata(c),
            "engineering": summarize(c),
            "end_face_geometry": evaluate_end_face(c),
            "whole_label_focus": evaluate_label_focus(c),
            "comparison_f8": evaluate_label_focus(c, 8),
        }
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Расчёты сохранены: {path}")
    elif args.command == "benchmark":
        from .benchmark import run

        run(args.output, args.boxes, args.seed)
        print(f"Результаты эксперимента: {args.output}")
    else:
        from .worker import decode_file_bounded

        try:
            readings = decode_file_bounded(
                args.image, args.timeout, enhanced=args.enhanced, formats=args.formats
            )
        except (ValueError, TimeoutError) as error:
            p.error(str(error))
        print(json.dumps(readings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
