from barcode_reader.scheduling import arrivals,simulate

def test_schedule_includes_acquisition_and_transfer():
    jobs=arrivals(1)
    assert len(jobs)==38
    assert abs(max(j.arrival for j in jobs)-2.0925539)<1e-7
    assert all(j.deadline==2.65 for j in jobs)

def test_queue_overload_cancels_box_and_stays_bounded():
    result=simulate(arrivals(10),lambda j:1.,workers=1,capacity=4)
    assert result['max_queue']<=4
    assert result['cancelled_boxes']>0
    assert any(o['late'] for o in result['outcomes'])

def test_parallel_processing_delivers_nominal_service():
    r=simulate(arrivals(20),lambda j:.28 if j.kind=='area' else .09,workers=8)
    assert not any(o['late'] for o in r['outcomes'])
