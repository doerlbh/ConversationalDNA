"""Create a tiny, explicitly synthetic demo without downloading any corpus.

Synthetic examples illustrate interface operations; they are never benchmark
observations or substitutes for the recorded full-corpus measurements.
"""
from pathlib import Path
import collections,json,sqlite3,sys
from representation import features,graph_stats,slice_episode,signature

def main():
    dst=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'app/demo.sqlite'
    if dst.exists():print('Existing sample database retained:',dst);return
    db=sqlite3.connect(dst);db.executescript('CREATE TABLE conversations(id TEXT PRIMARY KEY,corpus TEXT,nturns INTEGER,nspeakers INTEGER,nedges INTEGER,nonadjacent INTEGER,payload TEXT,title TEXT);CREATE VIRTUAL TABLE text_index USING fts5(text);CREATE TABLE episodes(id INTEGER PRIMARY KEY,cid TEXT,corpus TEXT,start INTEGER,stop INTEGER,signature TEXT);CREATE VIRTUAL TABLE motif_index USING fts5(tokens);CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
    examples=[
      [('S1','question','Which train should we take to the conference?'),('S2','clarify','Do we need to arrive before the opening talk?'),('S3','comment','I can book the tickets for everyone.'),('S1','answer','Yes, we need to arrive before nine.'),('S2','propose','Then the 7:30 departure gives us enough time.'),('S1','acknowledge','Agreed. Please book that departure.')],
      [('S1','question','Which room should we reserve for the workshop?'),('S2','clarify','Will everyone need a power outlet?'),('S3','comment','I will organize the sign-up list.'),('S1','answer','Yes, each person will bring a laptop.'),('S2','propose','Then room B has enough outlets.'),('S1','acknowledge','Agreed. Please reserve room B.')],
      [('S1','question','How should we divide the presentation?'),('S2','clarify','Do we have ten minutes in total?'),('S3','comment','I can cover the examples.'),('S1','answer','Yes, ten minutes including questions.'),('S2','propose','Then let us keep the overview to two minutes.'),('S1','acknowledge','That sounds workable.')],
      [('S1','question','Which day works for the team meeting?'),('S2','clarify','Does it need to include the remote team?'),('S3','comment','I am available on Wednesday.'),('S1','answer','Yes, we should include everyone.'),('S2','propose','Then Wednesday afternoon is the overlap.'),('S1','acknowledge','Let us confirm the time with them.')]]
    corpora=collections.defaultdict(collections.Counter);eid=0
    for n,items in enumerate(examples):
        ts=[dict(id=i,text=text,speaker=s,action=a,annotation='synthetic-example') for i,(s,a,text) in enumerate(items)]
        es=[dict(source=s,target=t,type=typ,provenance='synthetic-example') for s,t,typ in [(1,0,'Clarification_question'),(2,0,'Comment'),(3,1,'QAP'),(4,3,'Comment'),(5,4,'Acknowledgement')]]
        c=dict(id=f'synthetic:example-{n+1}',source_id=f'example-{n+1}',corpus='synthetic',turns=ts,edges=es,meta=dict(synthetic=True,source='Written illustrative examples; not collected conversations'))
        insert(db,c);eid+=1;ep=slice_episode(c);db.execute('INSERT INTO episodes VALUES (?,?,?,?,?,?)',(eid,c['id'],c['corpus'],0,len(ts),signature(ep)));db.execute('INSERT INTO motif_index(rowid,tokens) VALUES (?,?)',(eid,features(ep)));update(corpora,c)
    ts=[dict(id=i,text=text,speaker=s,action=a,annotation='synthetic-example') for i,(s,a,text) in enumerate([('S1','user','Please suggest a three-item packing list for a day hike.'),('S2','assistant','Water, a weatherproof layer, and a charged phone.'),('S1','user','Make it a winter hike.'),('S2','assistant','Water in an insulated bottle, a warm weatherproof layer, and a charged phone.')])]
    c=dict(id='synthetic_variants:example-1',source_id='example-1',corpus='synthetic_variants',turns=ts,edges=[dict(source=i,target=i-1,type='temporal',provenance='chronological') for i in range(1,4)],meta=dict(synthetic=True,source='Synthetic alternatives for interface demonstration; scores are absent',variants=[dict(turn=0,round=0,replies=[dict(text=ts[1]['text'],model='Illustrative response A',score=None,chosen=True),dict(text='Comfortable shoes, a map, and a small first-aid kit.',model='Illustrative response B',score=None,chosen=False)])],ambiguous_rounds=[]))
    insert(db,c);eid+=1;ep=slice_episode(c);db.execute('INSERT INTO episodes VALUES (?,?,?,?,?,?)',(eid,c['id'],c['corpus'],0,len(ts),signature(ep)));db.execute('INSERT INTO motif_index(rowid,tokens) VALUES (?,?)',(eid,features(ep)));update(corpora,c)
    stats={k:dict(v,name='Synthetic interaction examples' if k=='synthetic' else 'Synthetic response variants',example_ids=[]) for k,v in corpora.items()};stats['_build']=dict(synthetic=True,schema_version='0.1',window=12,stride=6)
    db.execute('INSERT INTO metadata VALUES (?,?)',('stats',json.dumps(stats)));db.commit();db.close();print('Created explicitly synthetic sample:',dst)

def insert(db,c):
    st=graph_stats(c);cur=db.execute('INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)',(c['id'],c['corpus'],len(c['turns']),st['speakers'],st['edges'],st['nonadjacent'],json.dumps(c),c['turns'][0]['text']))
    db.execute('INSERT INTO text_index(rowid,text) VALUES (?,?)',(cur.lastrowid,'\n'.join(t['text'] for t in c['turns'])))
def update(stats,c):
    s=graph_stats(c);stats[c['corpus']].update(conversations=1,turns=s['turns'],episodes=1,multiparty=int(s['speakers']>=3),eligible=1)
if __name__=='__main__':main()
