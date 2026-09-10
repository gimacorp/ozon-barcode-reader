"""Фактический прогон ZXing-C++; синтетические метрики не равны складским."""

import csv
import json
import platform
import time
from importlib.metadata import version
from pathlib import Path
import cv2
import numpy as np
from .decoder import decode
from .synthetic import dataset
from .metrics import key_record, wilson


def run(output="results", boxes=60, seed=20260909):
    out=Path(output); out.mkdir(parents=True,exist_ok=True)
    examples=out/"examples"; examples.mkdir(exist_ok=True)
    rows=[]; ledger=[]
    cv2.setNumThreads(1)
    # Один прогрев, вне тайминга. Генерация изображений также вне тайминга.
    decode(np.full((100,100),255,np.uint8))
    for i, sample in enumerate(dataset(seed,boxes)):
        expected={("Code 128",x.encode().hex()) for x in sample["expected"]}
        predictions={}
        for name,frames,enhanced,diagonal in [("one_frame",sample["frames"][1:2],False,False),
                                      ("three_frames",sample["frames"],False,False),
                                      ("three_frames_enhanced",sample["frames"],True,False),
                                      ("three_frames_diagonal",sample["frames"],False,True)]:
            started=time.perf_counter()
            found={d.key for frame in frames for d in decode(frame,enhanced,try_diagonal=diagonal,
                                                              formats="Code128" if diagonal else None)}
            elapsed=(time.perf_counter()-started)*1000
            predictions[name]=[key_record(k) for k in sorted(found)]
            rows.append({"box_id":sample["box_id"],"level":sample["level"],"method":name,
                         "expected":len(expected),"tp":len(found&expected),"fp":len(found-expected),
                         "fn":len(expected-found),"exact":int(found==expected),"latency_ms":elapsed})
        ledger.append({"box_id":sample["box_id"],"level":sample["level"],
                       "expected":[key_record(k) for k in sorted(expected)],"predictions":predictions})
        if i<3:
            for k,frame in enumerate(sample["frames"]):
                cv2.imwrite(str(examples/f"{sample['box_id']}_{k}.png"),frame)
            (examples/f"{sample['box_id']}.json").write_text(json.dumps({k:v for k,v in sample.items()
                if k!="frames"}|{"predictions":predictions},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if (i+1)%10==0:
            print(f"Обработано коробок: {i+1}/{boxes}",flush=True)
    with (out/"benchmark.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    (out/"predictions.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in ledger),encoding="utf-8")
    metrics=[]
    for method in dict.fromkeys(r["method"] for r in rows):
        for level in ("all","clean","moderate","hard"):
            rs=[r for r in rows if r["method"]==method and (level=="all" or r["level"]==level)]
            if not rs:continue
            tp=sum(r["tp"] for r in rs);fp=sum(r["fp"] for r in rs);fn=sum(r["fn"] for r in rs)
            metrics.append({"method":method,"level":level,"boxes":len(rs),"codes":tp+fn,
                            "exact_set_rate":sum(r["exact"] for r in rs)/len(rs),
                            "exact_ci95":wilson(sum(r["exact"] for r in rs),len(rs)),
                            "code_recall":tp/(tp+fn),"recall_ci95":wilson(tp,tp+fn),"code_precision":tp/(tp+fp) if tp+fp else None,
                            "false_values":fp,"latency_p50_ms":float(np.percentile([r["latency_ms"] for r in rs],50)),
                            "latency_p95_ms":float(np.percentile([r["latency_ms"] for r in rs],95))})
    result={"seed":seed,"boxes":boxes,"frames_per_box":3,"image_shape":[960,1280],
            "methods_note":"A-C: автоматический набор ZXing-C++, исходная ориентация. D: исходный кадр + 45°, явный перечень Code128. В D одновременно изменены поиск угла и перечень символик.",
            "warning":"Синтетика: кадры независимо изменены, физическая последовательность движения не моделируется. Тайминг полного цикла декодирования, без камеры, генерации и передачи.",
            "environment":{"python":platform.python_version(),"platform":platform.platform(),
                           "machine":platform.machine(),"processor":platform.processor(),
                           "opencv_threads":1,"packages":{p:version(p) for p in ["numpy","opencv-python-headless","zxing-cpp","python-barcode"]}},
            "metrics":metrics}
    (out/"benchmark.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result
