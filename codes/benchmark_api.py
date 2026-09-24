"""Measure actual localhost HTTP requests; excludes browser paint and cold start."""
import json, platform, random, time, urllib.request
from pathlib import Path
import numpy as np

BASE='http://127.0.0.1:8765'
OUT=Path(__file__).resolve().parents[1]/'results'
def call(path,body=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    t=time.perf_counter()
    with urllib.request.urlopen(req,timeout=30) as r:d=json.load(r)
    return d,(time.perf_counter()-t)*1000
def main():
    stats,_=call('/api/stats');queries=['installation','evidence','question','function','thanks','explain','group','problem','answer','code'];search=[];align=[]
    for q in queries:
        for _ in range(3):
            d,ms=call('/api/conversations?q='+q);search.append(dict(q=q,ms=ms,returned=d['returned']))
    for corpus in ['molweni','reddit','dailydialog','deli','wildchat']:
        examples,_=call('/api/conversations?corpus='+corpus+'&limit=8')
        for row in examples['results']:
            body=dict(id=row['id'],start=0,stop=min(12,row['nturns']),corpus=corpus)
            d,ms=call('/api/match',body);align.append(dict(id=row['id'],ms=ms,candidates=d['candidates']))
    quant=lambda xs:{'p50':float(np.median(xs)),'p95':float(np.quantile(xs,.95)),'max':max(xs),'n':len(xs)}
    result=dict(protocol='Warm localhost HTTP requests; text search over full record index; 40 structural requests within five corpora. No browser rendering, concurrency, cold disk or network latency claims.',search_ms=quant([r['ms'] for r in search]),alignment_ms=quant([r['ms'] for r in align]),corpus_stats=stats,environment=platform.platform(),search_requests=search,alignment_requests=align)
    (OUT/'api_benchmark.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ['search_ms','alignment_ms']}))
if __name__=='__main__':main()
