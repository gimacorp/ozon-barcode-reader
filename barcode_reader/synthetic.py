"""Независимый генератор Code 128 и детерминированных синтетических коробок."""

import cv2
import numpy as np
from barcode import Code128
from PIL import Image


def label(payload: str, module_px: float = 3.0):
    bits = Code128(payload).build()[0]
    scale = 6
    canvas = np.full((72*scale, (len(bits)+24)*scale), 255, np.uint8)
    for x, bit in enumerate(bits):
        if bit == "1":
            canvas[8*scale:64*scale, (12+x)*scale:(13+x)*scale] = 0
    return cv2.resize(canvas, (round((len(bits)+24)*module_px), round(72*module_px)),
                      interpolation=cv2.INTER_AREA)


def scene(payloads, rng, level, frame_index):
    """1280×960; все коды находятся внутри кадра. Размещение не дано декодеру."""
    canvas = np.full((960, 1280), 178, np.uint8)
    # В каждой ячейке свой код, включая вертикальный и наклонный.
    centers = [(320,250),(940,250),(320,720),(940,720)]
    for i, payload in enumerate(payloads):
        module = rng.uniform(2.0, 3.4) if level == "clean" else rng.uniform(1.25,2.7)
        stamp = Image.fromarray(label(payload, module))
        angle = float(rng.choice([0,90,-90,15,-20,35]))
        stamp = np.array(stamp.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=178))
        # Трапеция моделирует наклон плоской этикетки; её положение неизвестно reader.
        h,w = stamp.shape
        a = 0 if level == "clean" else rng.uniform(0,.11)*min(h,w)
        src = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
        dst = np.float32([[a,0],[w-1-a,a],[w-1,h-1-a],[0,h-1]])
        stamp = cv2.warpPerspective(stamp, cv2.getPerspectiveTransform(src,dst),(w,h),borderValue=178)
        if h>450 or w>590:
            ratio=min(450/h,590/w)
            stamp=cv2.resize(stamp,None,fx=ratio,fy=ratio,interpolation=cv2.INTER_AREA)
            h,w=stamp.shape
        cx,cy=centers[i]
        canvas[cy-h//2:cy-h//2+h,cx-w//2:cx-w//2+w]=stamp
    if level != "clean":
        # Независимые условия кадров дают возможность восстановить множество.
        blur = int(rng.choice([1,3,5,7,11] if level == "hard" else [1,1,3,5]))
        kernel=np.zeros((blur,blur),np.float32)
        kernel[blur//2,:]=1/blur
        canvas=cv2.filter2D(canvas,-1,kernel)
        contrast=rng.uniform(.18,.65) if level == "hard" else rng.uniform(.55,.95)
        canvas=128+(canvas.astype(np.float32)-128)*contrast
        noise=rng.normal(0, rng.uniform(1,9),canvas.shape)
        canvas=np.clip(canvas+noise,0,255).astype(np.uint8)
        if level == "hard":
            x=int(rng.integers(100,1150))
            canvas[:,x:x+75]=np.maximum(canvas[:,x:x+75],225)
    return canvas


def dataset(seed=20260909, boxes=60):
    if boxes < 1:
        raise ValueError("Нужна хотя бы одна коробка")
    rng=np.random.default_rng(seed)
    for i in range(boxes):
        level=("clean","moderate","hard")[i%3]
        payloads=[f"OZ{i:04d}{j:02d}" for j in range(1,1+int(rng.integers(1,5)))]
        yield {"box_id":f"SYN-{i:04d}", "level":level, "expected":payloads,
               "frames":[scene(payloads,rng,level,k) for k in range(3)]}
