"""Наглядный лист чтения из сохранённого полноразмерного кадра."""
from pathlib import Path
import os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
import numpy as np
from barcode_reader.decoder import decode

def run():
    raw=cv2.imread(str(ROOT/'results/nominal_frame.png'),0);ds=decode(raw)
    fig=plt.figure(figsize=(12,6),layout='constrained');gs=fig.add_gridspec(3,2,width_ratios=[1.1,1])
    ax=fig.add_subplot(gs[:,0]);ax.imshow(raw,cmap='gray');ax.set_title('Полный кадр 9344 × 7000',fontsize=17);ax.axis('off')
    for i,d in enumerate(ds):
        pts=np.asarray(d.polygon);ax.plot(*np.r_[pts,pts[:1]].T,color='#005BFF',lw=2)
        ax.annotate(str(i+1),xy=pts.mean(0),xytext=pts.mean(0)+[700,0],fontsize=17,color='#005BFF',arrowprops={'arrowstyle':'->','color':'#005BFF'})
        lo=np.maximum(0,np.floor(pts.min(0)-50)).astype(int);hi=np.minimum([raw.shape[1],raw.shape[0]],np.ceil(pts.max(0)+50)).astype(int)
        bx=fig.add_subplot(gs[i,1]);bx.imshow(raw[lo[1]:hi[1],lo[0]:hi[0]],cmap='gray',vmin=0,vmax=255)
        bx.set_title(f'{i+1}. {d.text} · {d.format}',fontsize=16);bx.axis('off')
    fig.savefig(ROOT/'docs/figures/nominal_reading.png',dpi=180);plt.close(fig)
if __name__=='__main__':run()
