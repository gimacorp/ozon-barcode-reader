import numpy as np
import pytest
from barcode_reader.decoder import decode,decode_strips,strips
from barcode_reader.synthetic import label


@pytest.mark.parametrize("turns",[0,1,2,3])
def test_real_decoder_rotations(turns):
    image=np.rot90(label("TEST000001",3),turns).copy()
    result=decode(image)
    assert {d.text for d in result}=={"TEST000001"}
    assert result[0].payload_hex==b"TEST000001".hex()


def test_multiple_symbols():
    canvas=np.full((600,900),255,np.uint8)
    for i,text in enumerate(["BOX000001","BOX000002"]):
        stamp=label(text,2)
        canvas[30+300*i:30+300*i+stamp.shape[0],30:30+stamp.shape[1]]=stamp
    assert {d.text for d in decode(canvas)}=={"BOX000001","BOX000002"}


def test_blank_and_invalid():
    assert decode(np.full((300,300),255,np.uint8))==[]
    with pytest.raises(ValueError):decode(np.zeros((0,0),np.uint8))


def test_strip_overlap_preserves_rotated_symbol():
    stamp=np.rot90(label("BOTTOM0001",2)).copy()
    canvas=np.full((1600,300),255,np.uint8)
    y=550
    canvas[y:y+stamp.shape[0],30:30+stamp.shape[1]]=stamp
    ds=decode_strips(canvas,800,400)
    assert [d.text for d in ds]==["BOTTOM0001"]
    assert min(y for x,y in ds[0].polygon)>=550


def test_strip_bounds():
    a=np.zeros((10,3),np.uint8)
    assert [i for i,_ in strips(a,6,2)]==[0,4]
    with pytest.raises(ValueError):list(strips(a,2,2))
