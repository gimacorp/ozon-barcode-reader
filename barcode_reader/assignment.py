"""Назначение ROI коробке в откалиброванных координатах конвейера, мм."""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class FaceRegion:
    box_id: str
    face: str
    bounds: tuple[float, float, float, float]

class Assigner:
    def __init__(self): self.assigned={}

    def assign(self, camera, frame_id, roi_id, polygon, image_to_face, regions):
        """Четыре угла ROI должны принадлежать одной области грани.

        Матрица 3×3 приходит из калибровки и энкодерного положения коробки.
        На границах/перекрытиях результат ambiguous; повтор одного ROI сохраняет владельца.
        """
        p=np.asarray(polygon,float)
        if p.shape!=(4,2) or not np.isfinite(p).all(): raise ValueError('Неверный ROI')
        q=np.c_[p,np.ones(4)]@np.asarray(image_to_face,float).T
        if not np.isfinite(q).all() or np.any(abs(q[:,2])<1e-9): return None
        q=q[:,:2]/q[:,2,None]
        matches=[]
        for r in regions:
            x0,y0,x1,y1=r.bounds
            if np.all((q[:,0]>x0)&(q[:,0]<x1)&(q[:,1]>y0)&(q[:,1]<y1)):
                matches.append((r.box_id,r.face))
        if len(matches)!=1: return None
        key=(camera,frame_id,roi_id)
        if key in self.assigned and self.assigned[key]!=matches[0]: return None
        self.assigned[key]=matches[0]
        return matches[0]


def observe_assigned(assigner, tracker, *, camera, frame_id, roi_id, detection,
                     image_to_face, regions, captured_s, completed_s, evidence=None):
    """Связка геометрического назначения и приёма результата трекером."""
    owner=assigner.assign(camera,frame_id,roi_id,detection.polygon,image_to_face,regions)
    if owner is None:return False
    box_id,face=owner
    return tracker.observe(box_id,face,frame_id,captured_s,completed_s,[detection],evidence=evidence)
