"""Командный интерфейс: python -m barcode_reader --help."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
import cv2
from .engineering import load_config,summarize
from .geometry import evaluate_end_face,evaluate_label_focus
from .decoder import decode


def main():
    p=argparse.ArgumentParser(description="Прототип шестистороннего чтения штрихкодов")
    sub=p.add_subparsers(dest="command",required=True)
    calc=sub.add_parser("calculate",help="Пересчитать геометрию и инженерные бюджеты")
    calc.add_argument("--config",default="configs/conveyor.json")
    calc.add_argument("--output",default="results/calculations.json")
    bench=sub.add_parser("benchmark",help="Запустить воспроизводимый синтетический эксперимент")
    bench.add_argument("--boxes",type=int,default=60);bench.add_argument("--seed",type=int,default=20260909)
    bench.add_argument("--output",default="results")
    read=sub.add_parser("decode",help="Прочитать все коды на изображении")
    read.add_argument("image");read.add_argument("--enhanced",action="store_true")
    args=p.parse_args()
    if args.command=="calculate":
        c=load_config(args.config);result={"engineering":summarize(c),"end_face_geometry":evaluate_end_face(c),
                                          "whole_label_focus":evaluate_label_focus(c),
                                          "comparison_f8":evaluate_label_focus(c,8)}
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"Расчёты сохранены: {path}")
    elif args.command=="benchmark":
        from .benchmark import run
        run(args.output,args.boxes,args.seed)
        print(f"Результаты эксперимента: {args.output}")
    else:
        image=cv2.imread(args.image,cv2.IMREAD_GRAYSCALE)
        if image is None:p.error("Не удалось открыть изображение")
        print(json.dumps([asdict(d) for d in decode(image,args.enhanced)],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
