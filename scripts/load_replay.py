"""Реальное декодирование в восьми процессах по расписанию + модель длинной очереди."""
from pathlib import Path
import sys,json,time,os,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from barcode_reader.scheduling import arrivals,simulate
from barcode_reader.synthetic import label
from barcode_reader.decoder import decode

FRAMES={}
def init_worker():
    cv2.setNumThreads(1)
    for kind,h,w in [('area',7000,9344),('line',2048,8192)]:
        image=np.full((h,w),255,np.uint8)
        for i in range(4):
            stamp=label(f'LOAD{i:04d}',3.86);sh,sw=stamp.shape
            x=100+(i%2)*(w//2);y=100+(i//2)*(h//2)
            image[y:y+sh,x:x+sw]=stamp
        FRAMES[kind]=image
    decode(np.full((100,100),255,np.uint8))

def work(kind):
    a=time.monotonic();d=decode(FRAMES[kind]);b=time.monotonic()
    return {'kind':kind,'start':a,'end':b,'service_s':b-a,'correct':{x.text for x in d}=={f'LOAD{i:04d}' for i in range(4)}}

def run(boxes=12,workers=8):
    jobs=arrivals(boxes);measurements=[];pending=[];cancelled=set();maxq=0
    with ProcessPoolExecutor(max_workers=workers,initializer=init_worker) as pool:
        # Все процессы прогреты до включения секундомера расписания.
        list(pool.map(work,['line']*(workers*2)))
        start=time.monotonic()
        for j in jobs:
            delay=start+j.arrival-time.monotonic()
            if delay>0:time.sleep(delay)
            current=[]
            for old,f in pending:
                if f.done():
                    r=f.result();measurements.append(r|{'box':old.box,'arrival':old.arrival,'deadline':old.deadline})
                else:current.append((old,f))
            pending=current
            if len(pending)>=64:cancelled.add(j.box);continue
            pending.append((j,pool.submit(work,j.kind)));maxq=max(maxq,len(pending))
        for j,f in pending:
            r=f.result();measurements.append(r|{'box':j.box,'arrival':j.arrival,'deadline':j.deadline})
    outcomes=[]
    for b in range(boxes):
        rs=[r for r in measurements if r['box']==b];ack=max(r['end'] for r in rs)-start+.05
        outcomes.append({'box':b,'finish_after_last_exposure_ms':(ack-(b*2+2.0125539))*1000,
                         'ack_s':ack,'late':ack>b*2+2.65 or b in cancelled,'jobs':len(rs)})
    service={k:[r['service_s'] for r in measurements if r['kind']==k] for k in ('area','line')}
    models=[]
    for count in (1,4,8):
        for multiplier in (1.,1.5,2.):
            sim=simulate(arrivals(1000),lambda j:float(np.percentile(service[j.kind],95))*multiplier,count)
            lat=[(o['ack_s']-(o['box']*2+2.0125539))*1000 for o in sim['outcomes'] if not o['late']]
            models.append({'workers':count,'service_multiplier':multiplier,'boxes':1000,
                'late_fraction':sum(x['late'] for x in sim['outcomes'])/1000,'max_queue':sim['max_queue'],
                'p95_success_ms':float(np.percentile(lat,95)) if lat else None})
    lat=[r['finish_after_last_exposure_ms'] for r in outcomes]
    result={'cpu':'Apple M5','workers':workers,'boxes':boxes,'interval_s':2,'capacity':64,'peak_inflight_including_running':maxq,
        'p95_ms':float(np.percentile(lat,95)),'p99_ms':float(np.percentile(lat,99)),
        'late_fraction':sum(r['late'] for r in outcomes)/boxes,'all_decodes_correct':all(r['correct'] for r in measurements),
        'service_p50_ms':{k:float(np.percentile(v,50))*1000 for k,v in service.items()},
        'service_p95_ms':{k:float(np.percentile(v,95))*1000 for k,v in service.items()},
        'outcomes':outcomes,'models':models,'measurements':[r|{'start':r['start']-start,'end':r['end']-start} for r in measurements],
        'scope':'Реальные CPU-вызовы декодера, 4 кода на изображение, кэшированные полные массивы в процессах. Приходы соответствуют камерам, включая 80 мс передачи торцов и 2 мс DMA полос. Физическая передача, shared-memory DMA и SDK отсутствуют. Реальный replay регистрирует все просрочки; отмена по сроку проверяется отдельно моделью EDF. p99 на малой выборке описательный.'}
    (ROOT/'results/load_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('outcomes','models','measurements')})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--boxes',type=int,default=12);a=parser.parse_args();run(a.boxes)
