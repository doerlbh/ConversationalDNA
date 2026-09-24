"""Research demo. Local by default; --host 0.0.0.0 enables container hosting."""
from pathlib import Path
import argparse, collections, json, os, re, sqlite3, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'codes'))
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.gzip import GZipMiddleware
from functools import lru_cache
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from representation import features, slice_episode
from retrieval import align, safe_fts

DEFAULT=Path.home()/'Library/CloudStorage/Dropbox/Git/data/dna_2026/processed/atlas.sqlite'
HERE=Path(__file__).parent
DB=Path(os.environ.get('DNA_DATABASE',DEFAULT if DEFAULT.exists() else HERE/'demo.sqlite'))
app=FastAPI(title='Conversational DNA',version='0.2.0')
app.add_middleware(GZipMiddleware,minimum_size=1000)

def atlas_path():
    return DB.with_name('demo_map.sqlite' if DB.name=='demo.sqlite' else 'atlas_map.sqlite')

@lru_cache(maxsize=3)
def atlas_payload(path,mtime):
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        data=dict(db.execute('SELECT key,value FROM meta'))
    return '{"summary":'+data['summary']+',"points":'+data['points']+'}'

@app.get('/api/atlas')
def atlas():
    path=atlas_path()
    if not path.exists():raise HTTPException(503,'Atlas map missing. Run codes/build_atlas.py for this database.')
    return Response(atlas_payload(str(path),path.stat().st_mtime_ns),media_type='application/json',headers={'Cache-Control':'no-cache'})

@app.get('/api/atlas/episode')
def atlas_episode(id:int=Query(ge=1)):
    path=atlas_path()
    if not path.exists():raise HTTPException(503,'Atlas map missing')
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;r=db.execute('SELECT * FROM atlas WHERE id=?',(id,)).fetchone()
        if not r:raise HTTPException(404,'Atlas episode not found')
        return dict(r)

@app.get('/api/atlas/pair')
def atlas_pair(corpus:str,from_:str=Query(alias='from',max_length=40),to:str=Query(max_length=40)):
    path=atlas_path()
    if not path.exists():raise HTTPException(503,'Atlas map missing')
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        r=db.execute('SELECT id FROM atlas WHERE corpus=? AND instr(pair_tokens,?)>0 ORDER BY speakers DESC,turns,id LIMIT 1',(corpus,'|'+from_+'>'+to+'|')).fetchone()
        if not r:raise HTTPException(404,'No indexed episode contains this pairing')
        return dict(r)

def connect():
    if not DB.exists():raise HTTPException(503,'Dataset index missing. Run codes/build_index.py or set DNA_DATABASE.')
    db=sqlite3.connect(f'file:{DB}?mode=ro',uri=True);db.row_factory=sqlite3.Row;return db
def fetch(db,cid):
    r=db.execute('SELECT payload FROM conversations WHERE id=?',(cid,)).fetchone()
    if not r:raise HTTPException(404,'Conversation not found')
    return json.loads(r[0])
def brief(row):return {k:row[k] for k in ['id','corpus','nturns','nspeakers','nedges','nonadjacent','title']}

@app.get('/api/stats')
def stats():
    with connect() as db:return json.loads(db.execute("SELECT value FROM metadata WHERE key='stats'").fetchone()[0])

@app.get('/api/conversations')
def search(q:str='',corpus:str='',motif:str='',limit:int=Query(24,ge=1,le=60)):
    t=time.perf_counter();params=[];where=[]
    if corpus:where.append('c.corpus=?');params.append(corpus)
    if motif=='delayed':where.append('c.nonadjacent>0')
    if motif=='group':where.append('c.nspeakers>=3')
    if motif=='variants':where.append("c.corpus IN ('prism','synthetic_variants')")
    if motif=='clarify':where.append("c.corpus IN ('molweni','synthetic') AND c.payload LIKE '%Clarification_question%'")
    fts=safe_fts(q)
    if fts:
        where.append('text_index MATCH ?');params.append(fts)
        sql='SELECT c.* FROM text_index JOIN conversations c ON c.rowid=text_index.rowid'
        order=' ORDER BY text_index.rank'
    else:
        sql='SELECT c.* FROM conversations c';where.append('c.nturns>=4');order=''
    rows=[]
    with connect() as db:
        rows=db.execute(sql+(' WHERE '+' AND '.join(where) if where else '')+order+' LIMIT ?',params+[limit]).fetchall()
    return dict(results=[brief(r) for r in rows],returned=len(rows),ms=round((time.perf_counter()-t)*1000,2),limit=limit)

@app.get('/api/conversation')
def get_conversation(id:str):
    with connect() as db:return fetch(db,id)

class Override(BaseModel):
    turn:int=Field(ge=0,le=50000)
    action:str=Field(min_length=1,max_length=40)

class MatchRequest(BaseModel):
    id:str
    start:int=Field(0,ge=0)
    stop:int|None=None
    corpus:str=''
    graph:bool=True
    overrides:list[Override]=Field(default_factory=list,max_length=50)
    limit:int=Field(8,ge=1,le=20)

@app.post('/api/match')
def match(request:MatchRequest):
    t=time.perf_counter()
    with connect() as db:
        c=fetch(db,request.id)
        stop=request.stop if request.stop is not None else min(request.start+12,len(c['turns']))
        if not 0<=request.start<stop<=len(c['turns']) or stop-request.start>24:raise HTTPException(422,'Select between 1 and 24 turns within the conversation.')
        for o in request.overrides:
            if o.turn>=len(c['turns']):raise HTTPException(422,'Annotation turn outside conversation')
            c['turns'][o.turn]['action']=o.action;c['turns'][o.turn]['annotation']='user-overlay'
        query=slice_episode(c,request.start,stop)
        tokens=list(dict.fromkeys(features(query).split()))
        search=' OR '.join('"'+x+'"' for x in tokens)
        sql='SELECT e.* FROM motif_index JOIN episodes e ON e.id=motif_index.rowid WHERE motif_index MATCH ? AND e.cid<>?'
        params=[search,request.id]
        if request.corpus:sql+=' AND e.corpus=?';params.append(request.corpus)
        rows=db.execute(sql+' ORDER BY motif_index.rank LIMIT 120',params).fetchall()
        results=[];cache={}
        for r in rows:
            if r['cid'] not in cache:cache[r['cid']]=fetch(db,r['cid'])
            conv=cache[r['cid']];ep=slice_episode(conv,r['start'],r['stop']);a=align(query,ep,graph=request.graph)
            results.append(dict(id=r['cid'],corpus=r['corpus'],start=r['start'],stop=r['stop'],episode=ep,alignment=a))
        results.sort(key=lambda x:x['alignment']['score'],reverse=True)
        distinct=[];seen=set()
        for r in results:
            if r['id'] not in seen:distinct.append(r);seen.add(r['id'])
            if len(distinct)==request.limit:break
    return dict(query=query,results=distinct,candidates=len(rows),ms=round((time.perf_counter()-t)*1000,2),method='local-alignment+typed-edge-reranking-v0.1',graph=request.graph,overrides=[o.model_dump() for o in request.overrides])

@app.get('/api/health')
def health():return {'status':'ok','database_exists':DB.exists()}

@app.get('/')
def index():return FileResponse(HERE/'index.html')
app.mount('/static',StaticFiles(directory=HERE/'static'),name='static')

if __name__=='__main__':
    import uvicorn
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--host',default='127.0.0.1');args=p.parse_args()
    uvicorn.run(app,host=args.host,port=args.port)
