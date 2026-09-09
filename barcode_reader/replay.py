"""Сквозной программный проход двух коробок через шесть направлений съёмки."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from .synthetic import label
from .decoder import decode
from .control import BoxTracker, MockPLC


def run_replay():
    """Снимки синтетические; box_id и времена задаются имитатором датчиков."""
    faces=[("top",0),("bottom",155),("left",30),("right",90),("front",45),("rear",120)]
    tracker,plc=BoxTracker(),MockPLC()
    results=[]
    for box_index in range(2):
        box_id=f"REPLAY-{box_index:02d}";start=box_index*2.
        tracker.register(box_id,start,start+1.8,start+2.635)
        expected=set()
        for face_index,(face,angle) in enumerate(faces):
            frame=np.full((1400,900),255,np.uint8)
            for label_index,y in enumerate((350,1050)):
                text=f"B{box_index}F{face_index}L{label_index}"
                expected.add(text)
                stamp=np.array(Image.fromarray(label(text,3.86)).rotate(angle,
                    expand=True,resample=Image.Resampling.BICUBIC,fillcolor=255))
                h,w=stamp.shape
                frame[y-h//2:y-h//2+h,450-w//2:450-w//2+w]=stamp
            readings=decode(frame)
            captured=start+.1+face_index*.25
            tracker.observe(box_id,face,f"{box_id}-{face}",captured,captured+.03,readings)
        message=tracker.finalize(box_id,start+2.)
        first=plc.receive(message,start+2.05)
        retry=plc.receive(message,start+2.1)
        results.append({"box_id":box_id,"expected":sorted(expected),"message":message,
                        "exact_set":{d["text"] for d in message["codes"]}==expected,
                        "first_ack":first,"retry_ack":retry})
    return {"description":"Две коробки, шесть граней, по две этикетки на грани; единая шкала времени имитатора.",
            "boxes":results,"commands":plc.commands,
            "limitation":"Привязку кадров к коробкам и временные метки задаёт имитатор. Аппаратный захват и сеть проверяются на пилоте."}


if __name__=="__main__":
    result=run_replay()
    path=Path("results/replay.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Полное множество: {sum(b['exact_set'] for b in result['boxes'])}/2 коробки. Команд: {len(result['commands'])}. {path}")
