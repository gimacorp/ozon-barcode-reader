"""Ограниченная очередь EDF: расчётное проигрывание расписания камер."""
from dataclasses import dataclass
import heapq

@dataclass(frozen=True)
class Job:
    box: int
    kind: str
    arrival: float
    deadline: float
    channel: str
    sequence: int


def arrivals(boxes=100,interval=2.):
    result=[]
    for b in range(boxes):
        base=b*interval;deadline=base+2.65
        for channel,x in [('top',.65),('left',.75),('right',.75),('bottom',.9)]:
            for i,offset in enumerate(range(0,7200-1024,1024)):
                result.append(Job(b,'line',base+x+min(offset+2048,7200)/12000+.002,deadline,channel,i))
        for channel,delay in [('front',0),('rear',.6)]:
            for i in range(5):
                result.append(Job(b,'area',base+1.2563039+delay+(i-2)/16+.03125+.08,deadline,channel,i))
    return sorted(result,key=lambda j:j.arrival)


def simulate(jobs,service,workers=8,capacity=64):
    """Последний ACK занимает 50 мс. Задачи после delivery deadline отменяются."""
    pending=[];active=[];finished={};cancelled=set();i=0;serial=0;maxq=0;now=0.;waits=[]
    while i<len(jobs) or active or pending:
        next_arrival=jobs[i].arrival if i<len(jobs) else float('inf')
        next_done=active[0][0] if active else float('inf')
        now=min(next_arrival,next_done)
        while active and active[0][0]<=now:
            end,_,j=heapq.heappop(active);finished[j.box]=max(finished.get(j.box,0),end)
        while i<len(jobs) and jobs[i].arrival<=now:
            j=jobs[i];i+=1
            if len(pending)>=capacity:cancelled.add(j.box)
            else:heapq.heappush(pending,(j.deadline,serial,j));serial+=1
        while pending and len(active)<workers:
            _,seq,j=heapq.heappop(pending)
            duration=service(j)
            if j.box in cancelled or now+duration+.05>j.deadline:
                cancelled.add(j.box);continue
            waits.append(now-j.arrival);heapq.heappush(active,(now+duration,seq,j))
        maxq=max(maxq,len(pending))
    boxes=sorted({j.box for j in jobs})
    outcomes=[{'box':b,'ack_s':finished.get(b,0)+.05,'late':b in cancelled or finished.get(b,0)+.05>next(j.deadline for j in jobs if j.box==b)} for b in boxes]
    return {'outcomes':outcomes,'max_queue':maxq,'max_wait_s':max(waits,default=0),'cancelled_boxes':len(cancelled)}
