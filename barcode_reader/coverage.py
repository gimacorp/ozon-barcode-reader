"""Контракт захвата и происхождение независимых наблюдений."""
from dataclasses import dataclass, field

LINE_FACES = frozenset({'top', 'bottom', 'left', 'right'})

@dataclass(frozen=True)
class Evidence:
    camera: str
    acquisition: str
    rows: tuple[int, int] | None = None  # Полуоткрытый диапазон исходного скана.

    def independent(self, other):
        if (self.camera, self.acquisition) != (other.camera, other.acquisition):
            return True
        if self.rows is None or other.rows is None:
            return False
        return self.rows[1] <= other.rows[0] or other.rows[1] <= self.rows[0]

@dataclass
class CaptureContract:
    area_frames: dict[str, set[str]] = field(default_factory=dict)
    line_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    processed_frames: dict = field(default_factory=dict)
    processed_rows: dict = field(default_factory=dict)

    @classmethod
    def production(cls, box_id, total_rows=7200):
        return cls({f:{f'{box_id}-{f}-{i}' for i in range(5)} for f in ('front','rear')},
                   {f:(0,total_rows) for f in LINE_FACES})

    @classmethod
    def image_demo(cls, frame_ids):
        """Явный контракт демонстрации: по одному площадному изображению на грань."""
        return cls({f:{fid} for f,fid in frame_ids.items()})

    def record(self, face, evidence, dropped_rows=()):
        if face in self.area_frames and evidence.rows is None:
            self.processed_frames.setdefault(face,set()).add(evidence.acquisition)
        if face in self.line_ranges and evidence.rows is not None:
            start,end=evidence.rows
            if not 0 <= start < end:
                raise ValueError('Неверный диапазон строк')
            # Пропущенные аппаратные номера вычитаются до объединения интервалов.
            cursor=start
            for row in sorted(set(dropped_rows)):
                if start <= row < end:
                    self.processed_rows.setdefault(face,[]).append((cursor,row)); cursor=row+1
            self.processed_rows.setdefault(face,[]).append((cursor,end))

    def complete_faces(self):
        result={f for f,ids in self.area_frames.items() if ids <= self.processed_frames.get(f,set())}
        for f,(start,end) in self.line_ranges.items():
            cursor=start
            for a,b in sorted(self.processed_rows.get(f,[])):
                if a > cursor: break
                cursor=max(cursor,b)
            if cursor >= end: result.add(f)
        return result


def independent_count(evidence):
    """Максимум непересекающихся интервалов в каждом исходном скане."""
    groups={}
    for e in evidence: groups.setdefault((e.camera,e.acquisition),set()).add(e.rows)
    total=0
    for intervals in groups.values():
        if None in intervals:
            total+=1
        else:
            end=-1
            for a,b in sorted(intervals,key=lambda r:r[1]):
                if a>=end: total+=1;end=b
    return total
