"""Оценка уникальных значений по символике и исходным байтам."""
import math

def key_record(key): return {'format':key[0],'payload_hex':key[1]}

def value_key(record): return record['format'],bytes.fromhex(record['payload_hex']).hex()

def score(expected, found):
    e,f=set(expected),set(found)
    return {'expected':len(e),'tp':len(e&f),'fp':len(f-e),'fn':len(e-f),'exact':int(e==f)}

def wilson(successes,total,z=1.959963984540054):
    if not total:return [None,None]
    p=successes/total;den=1+z*z/total
    center=(p+z*z/(2*total))/den
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0.,center-half),min(1.,center+half)]
