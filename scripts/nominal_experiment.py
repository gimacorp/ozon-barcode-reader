"""Постоянные этикетки, движение коробки, проектная проекция и оптические искажения."""
from pathlib import Path
import sys,json,math,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import cv2
from barcode import Code128
from barcode_reader.geometry import project
from barcode_reader.engineering import load_config,working_distance
from barcode_reader.optics import degrade,defocus_diameter
from barcode_reader.decoder import decode,decode_strips
from barcode_reader.metrics import score,wilson,key_record

def stamp(text):
    img=np.full((250,780),255,np.uint8)
    for i,b in enumerate(Code128(text).build()[0]):
        if b=='1':img[45:205,round((12+i)*3.3):round((13+i)*3.3)]=0
    return img

def patch(text,angle,center):
    a=np.radians(angle);r=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    return np.array([[-39,-12.5],[39,-12.5],[39,12.5],[-39,12.5]])@r.T+center

def paste(canvas,img,uv,pixel,ap,coc,motion=.5):
    margin=32
    lo=np.floor(uv.min(0)).astype(int)-margin;hi=np.ceil(uv.max(0)).astype(int)+margin
    w,h=hi-lo
    src=np.float32([[0,0],[img.shape[1]-1,0],[img.shape[1]-1,img.shape[0]-1],[0,img.shape[0]-1]])
    roi=cv2.warpPerspective(img,cv2.getPerspectiveTransform(src,(uv-lo).astype(np.float32)),(w,h),borderValue=255)
    roi=degrade(roi,pixel,ap,coc,motion)
    x,y=lo;hh,ww=canvas.shape
    if x<0 or y<0 or x+w>ww or y+h>hh:raise ValueError('Этикетка за полем зрения')
    canvas[y:y+h,x:x+w]=np.minimum(canvas[y:y+h,x:x+w],roi)


def run(boxes=12):
    c=load_config();cv2.setNumThreads(1);rng=np.random.default_rng(20260909)
    wd=working_distance(50,9344*.0032,750);dx=math.sqrt(wd**2-350**2)
    pos=np.array([-dx,0.,550.]);target=np.array([0.,0.,200.]);fp=50*wd/(wd-50)/.0032
    rows=[];manifest=[];start=time.perf_counter()
    dest=ROOT/'docs/figures';dest.mkdir(exist_ok=True)
    for box in range(boxes):
        expected=set();found=set();perface=[]
        phase=np.linspace(-31.25,31.25,boxes)[box]
        for face_idx,face in enumerate(['top','bottom','left','right','front','rear']):
            labels=[]
            for i,center in enumerate(([(-115,65),(0,200),(115,335)] if face in ('front','rear') else [(80,80),(200,300),(320,520)])):
                text=f'N{box:02d}{face_idx}{i}';key=('Code 128',text.encode().hex());expected.add(key)
                angle=(box*15+i*45)%180
                labels.append((text,stamp(text),patch(text,angle,center)))
            fs=set();frames=[]
            shifts=(np.arange(5)-2)*62.5+phase if face in ('front','rear') else [0]
            for frame_index,shift in enumerate(shifts):
                area=face in ('front','rear');canvas=np.full((7000,9344) if area else (7200,8192),255,np.uint8)
                details=[]
                for text,img,corners in labels:
                    if area:
                        pts=np.c_[np.full(4,shift),corners]
                        uv,depth=project(pts,pos,target,fp,9344,7000)
                        coc=float(max(defocus_diameter(50,11,wd,depth,.0032)))
                        paste(canvas,img,uv,.0032,11,coc)
                    else:
                        fov=450 if face in ('left','right') else 700
                        focus=working_distance(28,8192*.0035,fov)
                        # Пограничный допуск: смещение + размер + yaw + roll + изгиб.
                        base=3+2+1.745+1 if fov==450 else (5+2+1 if face=='top' else -2)
                        depth=focus+base+(corners[:,1]-300)*math.sin(math.radians(.5))
                        uv=np.c_[4096+(corners[:,0]-200)*(8192/fov)*focus/depth,corners[:,1]*12]
                        coc=float(max(defocus_diameter(28,8,focus,depth,.0035)))
                        paste(canvas,img,uv,.0035,8,coc)
                    details.append({'text':text,'physical_corners_mm':corners.tolist(),'image_corners_px':uv.tolist(),'coc_px':coc})
                readings=decode(canvas) if area else decode_strips(canvas)
                fs|={d.key for d in readings}
                frames.append({'frame':frame_index,'shift_mm':float(shift),'detections':[key_record(d.key) for d in readings], 'labels':details})
                if box==0 and face=='rear' and frame_index==2:
                    # Полный кадр сохраняется без изменения разрешения; рамки в отдельном превью.
                    cv2.imwrite(str(ROOT/'results/nominal_frame.png'),canvas)
                    view=cv2.cvtColor(canvas,cv2.COLOR_GRAY2BGR)
                    for d in readings:
                        p=np.int32(d.polygon);cv2.polylines(view,[p],True,(255,90,0),12)
                        cv2.putText(view,d.text,tuple(p[0]),cv2.FONT_HERSHEY_SIMPLEX,3,(255,90,0),6)
                    cv2.imwrite(str(dest/'nominal_reading.png'),cv2.resize(view,(1402,1050)))
            found|=fs;perface.append({'face':face,'found':len(fs),'expected':3})
            manifest.append({'box':box,'face':face,'phase_mm':float(phase),'frames':frames})
        rows.append({'box':box,**score(expected,found),'faces':perface})
        print(f'Номинальная коробка {box+1}/{boxes}: {len(found)}/18',flush=True)
    exact=sum(r['exact'] for r in rows);tp=sum(r['tp'] for r in rows)
    result={'seed':20260909,'boxes':boxes,'labels':boxes*18,'unique_values_found':tp,'exact_boxes':exact,
        'exact_ci95':wilson(exact,boxes),'rows':rows,'elapsed_s':time.perf_counter()-start,
        'model':'Каждая коробка имеет 18 постоянных этикеток; 4 полных линейных скана 8192×7200 и 10 торцевых кадров 9344×7000. Проекция тонкой линзы, проектный X=0.33 мм, консервативный дефокус по худшему углу этикетки; дифракция, апертура пикселя, смаз 0.5 px, условная аберрация sigma=0.35 px.',
        'limitations':'Плоские матовые этикетки, постоянное освещение, без шума фотонов, бликов, окклюзий и калибровочных ошибок. Проекции торцов симметричны. Скорость/позиции заданы моделью; это проверка согласованности проекта.'}
    (ROOT/'results/nominal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'results/nominal_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    from scripts.presentation_evidence import run as present
    present()
if __name__=='__main__':run()
