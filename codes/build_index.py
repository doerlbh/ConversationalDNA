"""Reproducible multi-corpus adapters and SQLite full-text/structural index.

All downloaded inputs and derived databases stay in the shared data directory.
The SQLite file is built under a temporary name, then atomically installed.
"""
from pathlib import Path
import argparse, collections, hashlib, itertools, json, math, os, sqlite3, time
import pyarrow.parquet as pq
from representation import MAPPING, canonical_speakers, features, graph_stats, slice_episode, signature

ROOT = Path.home()/'Library/CloudStorage/Dropbox/Git/data'
DATA = ROOT/'dna_2026'
CORPORA = {'molweni':'Molweni', 'reddit':'Reddit Coarse Discourse', 'cmv':'ChangeMyView',
           'deli':'DeliData', 'chromium':'Chromium', 'wildchat':'WildChat (one shard)',
           'prism':'PRISM', 'dailydialog':'DailyDialog (train)'}

def js(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def scalar(v): return v if isinstance(v,(str,int,bool)) or (isinstance(v,float) and math.isfinite(v)) else None
def turn(i,text,speaker,action='unknown',annotation='unannotated',**kw):
    return dict(id=i,text=str(text or ''),speaker=str(speaker),action=action,annotation=annotation,**kw)
def conversation(corpus,cid,turns,edges,**meta):
    canonical_speakers(turns)
    return dict(id=f'{corpus}:{cid}',source_id=str(cid),corpus=corpus,turns=turns,edges=edges,meta=meta)

def molweni(data):
    for split in ['train','dev','test']:
        for c in json.loads((data/'raw/molweni'/f'{split}.json').read_text()):
            ts=[turn(i,e['text'],e['speaker']) for i,e in enumerate(c['edus'])]
            es=[]
            for e in c['relations']:
                # Molweni x=parent, y=child. Preserve native labels on edges.
                ts[e['y']]['action']=MAPPING.get(e['type'],e['type'].lower())
                ts[e['y']]['annotation']='human-discourse';ts[e['y']]['native_label']=e['type']
                es.append(dict(source=e['y'],target=e['x'],type=e['type'],provenance='human-discourse'))
            yield conversation('molweni',split+'-'+str(c['id']),ts,es,split=split,source_dialogue_id=str(c['id']),order='source-utterance')

def convokit(data,name,short,stage):
    path=next((data/'raw'/name).rglob('utterances.jsonl'))
    # Disk grouping avoids assuming source records are contiguous by conversation.
    stage.execute('DROP TABLE IF EXISTS staging')
    stage.execute('CREATE TABLE staging(cid TEXT, ordinal INTEGER, uid TEXT, speaker TEXT, text TEXT, parent TEXT, action TEXT, annotation TEXT, native TEXT, extra TEXT)')
    batch=[]
    for i,line in enumerate(path.open()):
        u=json.loads(line); m=u.get('meta',{}); cid=str(u.get('conversation_id',u.get('root')))
        uid=str(u['id']); parent=u.get('reply-to',u.get('reply_to')); action='unknown'; provenance='unannotated'; native=None;extra={}
        if short=='reddit':
            native=scalar(m.get('majority_type'));action=native or 'unknown';provenance='human-majority'
            annotated_target=m.get('majority_link')
            if annotated_target not in (None,'none'):extra['annotated_target']=str(annotated_target)
        elif short=='deli':
            if m.get('message_type') != 'MESSAGE': continue
            native=scalar(m.get('annotation_type'));action=MAPPING.get(native,native) or 'unknown';provenance='human-deliberation'
            extra['annotation_target']=scalar(m.get('annotation_target'))
        batch.append((cid,i,uid,str(u.get('speaker',u.get('user','unknown'))),u.get('text',''),str(parent) if parent is not None else None,action,provenance,native,js(extra)))
        if len(batch)>=10000:
            stage.executemany('INSERT INTO staging VALUES (?,?,?,?,?,?,?,?,?,?)',batch); batch=[]
    if batch:stage.executemany('INSERT INTO staging VALUES (?,?,?,?,?,?,?,?,?,?)',batch)
    stage.execute('CREATE INDEX stage_cid ON staging(cid,ordinal)');stage.commit()
    metadata={}
    if short in ('cmv','deli','reddit'):
        mp=next((data/'raw'/name).rglob('conversations.json')); metadata=json.loads(mp.read_text())
    rows=stage.execute('SELECT * FROM staging ORDER BY cid,ordinal')
    for cid,group in itertools.groupby(rows,key=lambda x:x[0]):
        us=list(group); ids={u[2]:i for i,u in enumerate(us)};ts=[];es=[]
        for i,u in enumerate(us):
            _,_,uid,speaker,text,parent,action,annotation,native,extra=u; extra=json.loads(extra)
            ts.append(turn(i,text,speaker,action,annotation,source_id=uid,native_label=native))
            if parent in ids and ids[parent]!=i:
                prov='chronological' if short=='deli' else 'platform-reply'
                es.append(dict(source=i,target=ids[parent],type='temporal' if short=='deli' else 'reply',provenance=prov))
            target=extra.get('annotated_target')
            if target in ids and target!=parent and ids[target]!=i:
                es.append(dict(source=i,target=ids[target],type='discourse',provenance='human-link'))
        m=metadata.get(cid,{});m=m.get('meta',m)
        keep={k:m[k] for k in ('split','summary_meta','pair_id','has_removed_comment','team_performance','performance_change','title','subreddit') if k in m}
        yield conversation(short,cid,ts,es,order='source-file',**keep)

def wildchat(data):
    seen=set()
    f=pq.ParquetFile(data/'raw/wildchat-shard-00000.parquet')
    for batch in f.iter_batches(batch_size=256,columns=['conversation_hash','model','conversation','language','toxic']):
        for c in batch.to_pylist():
            if c['toxic']:continue
            # Content hashes deduplicate exact transcripts, not inferred persons.
            digest=hashlib.sha256(js([(t['role'],t['content']) for t in c['conversation']]).encode()).hexdigest()
            if digest in seen:continue
            seen.add(digest);ts=[];es=[]
            for i,t in enumerate(c['conversation']):
                ts.append(turn(i,t['content'],t['role'],t['role'],'source-role'))
                if i:es.append(dict(source=i,target=i-1,type='temporal',provenance='chronological'))
            if ts:yield conversation('wildchat',digest[:24],ts,es,language=c['language'],model=c['model'],source_hash=c['conversation_hash'],order='source-utterance',subset='shard-00000-of-00086')

def prism(root):
    for c in pq.read_table(root/'prism_alignment/conversations.parquet').to_pylist():
        ts=[];es=[];variants=[];ambiguous=[]
        grouped=collections.defaultdict(list)
        for t in c['conversation_history']:grouped[t['turn']].append(t)
        for rnd,group in sorted(grouped.items()):
            users=[t for t in group if t['role']=='user'];answers=[t for t in group if t['role']!='user']
            if not users:continue
            i=len(ts);ts.append(turn(i,users[0]['content'],'human','user','source-role',round=rnd))
            if i:es.append(dict(source=i,target=i-1,type='temporal',provenance='chronological'))
            variants.append(dict(turn=i,round=rnd,replies=[dict(text=t['content'],model=t.get('model_name'),score=t.get('score'),chosen=t.get('if_chosen'),source_candidate=t.get('within_turn_id')) for t in answers]))
            chosen=[t for t in answers if t.get('if_chosen')]
            if len(chosen)!=1:
                ambiguous.append(rnd);break
            t=chosen[0];j=len(ts);ts.append(turn(j,t['content'],'model','assistant','source-role',model=t.get('model_name'),round=rnd))
            es.append(dict(source=j,target=i,type='prompt-response',provenance='observed-alternative'))
        if ts:yield conversation('prism',c['conversation_id'],ts,es,variants=variants,ambiguous_rounds=ambiguous,order='unique-selected-path-until-ambiguity')

def daily(root):
    for c in pq.read_table(root/'dailydialog/train.parquet').to_pylist():
        ts=[turn(i,t,f'S{i%2+1}',MAPPING.get(str(a),'unknown'),'human-dialogue-act',native_label=str(a)) for i,(t,a) in enumerate(zip(c['utterances'],c['acts']))]
        es=[dict(source=i,target=i-1,type='temporal',provenance='chronological') for i in range(1,len(ts))]
        yield conversation('dailydialog',c['id'],ts,es,split='train',speaker_assignment='alternation-assumption',order='source-utterance')

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,default=DATA);p.add_argument('--skip-chromium',action='store_true');args=p.parse_args()
    data=args.data_root;out=data/'processed';out.mkdir(exist_ok=True)
    dest=out/'atlas.sqlite';temp=out/'atlas.building.sqlite'
    if temp.exists():raise SystemExit('A partial build exists. Inspect it before removing or resuming.')
    db=sqlite3.connect(temp);db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE; CREATE TABLE conversations(id TEXT PRIMARY KEY,corpus TEXT,nturns INTEGER,nspeakers INTEGER,nedges INTEGER,nonadjacent INTEGER,payload TEXT,title TEXT); CREATE VIRTUAL TABLE text_index USING fts5(text); CREATE TABLE episodes(id INTEGER PRIMARY KEY,cid TEXT,corpus TEXT,start INTEGER,stop INTEGER,signature TEXT); CREATE VIRTUAL TABLE motif_index USING fts5(tokens);')
    stage=sqlite3.connect(out/'staging.sqlite');stage.execute('PRAGMA journal_mode=OFF');stage.execute('PRAGMA synchronous=OFF')
    generators=[('molweni',molweni(data))]+[(short,convokit(data,n,short,stage)) for n,short in [('reddit-coarse-discourse-corpus','reddit'),('conversations-gone-awry-cmv-corpus','cmv'),('deli-corpus','deli')]]
    generators += [('wildchat',wildchat(data)),('prism',prism(data.parent)),('dailydialog',daily(data.parent))]
    if not args.skip_chromium:generators += [('chromium',convokit(data,'chromium-corpus','chromium',stage))]
    stats={};eid=0;t0=time.monotonic()
    for name,gen in generators:
        count=collections.Counter();lengths=[];sample_ids=[]
        for c in gen:
            s=graph_stats(c); count.update(conversations=1,turns=s['turns'],edges=s['edges'],nonadjacent=s['nonadjacent'],multiparty=int(s['speakers']>=3),eligible=int(s['turns']>=4));lengths.append(s['turns'])
            title=c['meta'].get('title') or c['turns'][0]['text'][:100].replace('\n',' ')
            cur=db.execute('INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)',(c['id'],name,s['turns'],s['speakers'],s['edges'],s['nonadjacent'],js(c),title))
            db.execute('INSERT INTO text_index(rowid,text) VALUES (?,?)',(cur.lastrowid,'\n'.join(t['text'] for t in c['turns'])))
            if len(c['turns'])>=4:
                # Up to 64 overlapping windows, size <=12 and stride 6. Never silently call this exhaustive.
                for start in list(range(0,len(c['turns'])-3,6))[:64]:
                    ep=slice_episode(c,start,min(start+12,len(c['turns'])));eid+=1
                    db.execute('INSERT INTO episodes VALUES (?,?,?,?,?,?)',(eid,c['id'],name,ep['start'],ep['stop'],signature(ep)))
                    db.execute('INSERT INTO motif_index(rowid,tokens) VALUES (?,?)',(eid,features(ep)));count['episodes']+=1
                if len(sample_ids)<8 and s['nonadjacent']>=2 and s['speakers']>=3:sample_ids.append(c['id'])
            if count['conversations']%25000==0:
                db.commit();print(name,count['conversations'],round(time.monotonic()-t0,1),flush=True)
        count['median_turns']=sorted(lengths)[len(lengths)//2] if lengths else 0;count['max_turns']=max(lengths,default=0)
        stats[name]=dict(count);stats[name]['name']=CORPORA[name];stats[name]['example_ids']=sample_ids
        print(name,dict(count),flush=True);db.commit()
    db.executescript('CREATE INDEX corpus_idx ON conversations(corpus,nturns,nspeakers); CREATE INDEX episode_cid ON episodes(cid); CREATE INDEX episode_corpus ON episodes(corpus); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);')
    stats['_build']=dict(seconds=round(time.monotonic()-t0,2),window=12,stride=6,max_windows_per_conversation=64,schema_version='0.1',created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    db.execute('INSERT INTO metadata VALUES (?,?)',('stats',js(stats)));db.commit();db.close();stage.close()
    os.replace(temp,dest);(out/'corpus_stats.json').write_text(json.dumps(stats,indent=2))
    print('DONE',dest,flush=True)

if __name__=='__main__':main()
