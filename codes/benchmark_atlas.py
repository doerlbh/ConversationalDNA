"""Measure full atlas transfer separately from browser parsing/rendering."""
from pathlib import Path
import gzip,json,platform,time,urllib.request
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=[]
    for i in range(10):
        req=urllib.request.Request('http://127.0.0.1:8765/api/atlas',headers={'Accept-Encoding':'gzip'})
        t=time.perf_counter()
        with urllib.request.urlopen(req,timeout=30) as response:wire=response.read();encoding=response.headers.get('Content-Encoding')
        transfer=(time.perf_counter()-t)*1000
        payload=gzip.decompress(wire) if encoding=='gzip' else wire
        d=json.loads(payload);total=(time.perf_counter()-t)*1000
        assert len(d['points'])==d['summary']['episodes']==151489
        rows.append(dict(transfer_ms=transfer,python_decode_ms=total-transfer,total_ms=total,encoding=encoding,wire_bytes=len(wire),json_bytes=len(payload)))
    out=dict(protocol='Ten sequential full-map localhost requests, warm process, Accept-Encoding gzip. Transfer includes service compression; decode uses Python, not the browser. No browser paint or concurrent-user claim.',environment=platform.platform(),episodes=d['summary']['episodes'],rows=rows,transfer_median_ms=float(np.median([r['transfer_ms'] for r in rows])),transfer_p95_ms=float(np.quantile([r['transfer_ms'] for r in rows],.95)))
    (ROOT/'results/atlas_transfer.json').write_text(json.dumps(out,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2));print(rows[-1])
if __name__=='__main__':main()
