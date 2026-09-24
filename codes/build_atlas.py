"""Full episode atlas: measured descriptors, PCA coordinates, and motif census.

Reads the immutable research index and writes a small sidecar. No text model,
topic inference, social outcome, or cross-corpus speaker identity is involved.
"""
from pathlib import Path
import argparse,collections,hashlib,json,math,re,sqlite3,time
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from representation import slice_episode,trusted_edges

FIELDS=['log_turns','speaker_fraction','speaker_switching','speaker_entropy','largest_speaker_share','known_action_fraction','target_density','nonadjacent_fraction','mean_target_span','max_target_span','branching_targets','clarification_fraction','answer_fraction','question_fraction','acknowledgement_fraction','proposal_fraction','action_entropy','mean_log_word_count','lexical_recurrence']
MOVE_GROUPS=['question','clarify','answer','comment','elaborate','acknowledge','correct','propose','probe','inform','directive','other','unknown']
def move(action):return action if action in MOVE_GROUPS else ('other' if action not in ['user','assistant','0','unknown'] else 'unknown')
def entropy(values):
    counts=collections.Counter(values);n=len(values)
    return -sum(v/n*math.log(v/n) for v in counts.values())/math.log(max(2,len(counts)))

def describe(ep):
    ts=ep['turns'];n=len(ts);speakers=[t['speaker'] for t in ts];counts=collections.Counter(speakers);es=trusted_edges(ep)
    labels=[move(t['action']) for t in ts];actions=collections.Counter(labels);lags=[abs(e['source']-e['target']) for e in es]
    degrees=collections.Counter(e['target'] for e in es);switch=sum(a!=b for a,b in zip(speakers,speakers[1:]))/max(1,n-1)
    reach=sum(lags)/len(lags) if lags else None;nonadj=sum(v>1 for v in lags);branch=sum(v>=2 for v in degrees.values())
    words=[re.findall(r'\b\w+\b',t['text'].lower()) for t in ts]
    recurrence=[len(set(a)&set(b))/max(1,len(set(a)|set(b))) for a,b in zip(words,words[1:])]
    feat=[math.log1p(n),len(counts)/n,switch,entropy(speakers),max(counts.values())/n,1-actions['unknown']/n,len(es)/n,nonadj/max(1,len(es)),(reach or 0)/max(1,n-1),max(lags,default=0)/max(1,n-1),branch/n,*[actions[a]/n for a in ['clarify','answer','question','acknowledge','propose']],entropy(labels),sum(math.log1p(len(w)) for w in words)/n,sum(recurrence)/max(1,len(recurrence))]
    # Motifs describe annotation configurations, never inferred successful repair.
    flags=int(len(counts)>=3)+2*int(nonadj>0)+4*int(actions['clarify']>0)+8*int(branch>0)+16*int(len(es)>0)
    pairs=collections.Counter((move(ts[e['target']]['action']),move(ts[e['source']]['action'])) for e in es)
    return feat,dict(turns=n,speakers=len(counts),switch=round(switch,4),reach=round(reach,3) if reach is not None else None,flags=flags,edges=len(es),nonadjacent=nonadj,known=round(1-actions['unknown']/n,4),branch=branch),pairs

def build(source,dest):
    started=time.time();src=sqlite3.connect(f'file:{source}?mode=ro',uri=True);src.row_factory=sqlite3.Row
    groups=src.execute('SELECT cid,COUNT(*) n FROM episodes GROUP BY cid').fetchall()
    rows=[];feats=[];pairs=collections.defaultdict(collections.Counter);corpora={};sample={}
    for gi,g in enumerate(groups):
        c=json.loads(src.execute('SELECT payload FROM conversations WHERE id=?',(g['cid'],)).fetchone()[0]);key=c['corpus']
        if key not in corpora:corpora[key]=len(corpora)
        for e in src.execute('SELECT id,start,stop FROM episodes WHERE cid=? ORDER BY start',(g['cid'],)):
            ep=slice_episode(c,e['start'],e['stop']);f,m,p=describe(ep);feats.append(f)
            rows.append(dict(id=e['id'],cid=c['id'],corpus=key,start=e['start'],stop=e['stop'],pair_tokens=''.join('|'+a+'>'+b+'|' for a,b in p),**m));pairs[key].update(p)
            if key not in sample or (m['flags']&4 and m['flags']&1 and m['turns']<=10):sample[key]=e['id']
        if gi%20000==0:print('atlas source records',gi,flush=True)
    x=np.array(feats,dtype=np.float64);scaler=StandardScaler();z=scaler.fit_transform(x);pca=PCA(n_components=2,svd_solver='full');coords=pca.fit_transform(z)
    lo=coords.min(axis=0);hi=coords.max(axis=0);coords=(coords-lo)/np.maximum(hi-lo,1e-9)
    temp=dest.with_suffix('.building.sqlite');db=sqlite3.connect(temp);db.executescript('DROP TABLE IF EXISTS atlas; DROP TABLE IF EXISTS meta; CREATE TABLE atlas(id INTEGER PRIMARY KEY,cid TEXT,corpus TEXT,start INTEGER,stop INTEGER,x REAL,y REAL,turns INTEGER,speakers INTEGER,switch REAL,reach REAL,flags INTEGER,edges INTEGER,nonadjacent INTEGER,known REAL,branch INTEGER,pair_tokens TEXT);CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);')
    points=[]
    for r,xy in zip(rows,coords):
        r.update(x=round(float(xy[0]),6),y=round(float(xy[1]),6));db.execute('INSERT INTO atlas VALUES (:id,:cid,:corpus,:start,:stop,:x,:y,:turns,:speakers,:switch,:reach,:flags,:edges,:nonadjacent,:known,:branch,:pair_tokens)',r)
        points.append([r['id'],r['x'],r['y'],corpora[r['corpus']],r['turns'],r['speakers'],r['switch'],r['reach'],r['flags'],r['edges'],r['nonadjacent'],r['known']])
    summary=dict(schema='dna-atlas/0.2',episodes=len(rows),source_records=len(groups),corpora=list(corpora),features=FIELDS,projection='PCA of 19 standardized episode descriptors; full indexed episode population',explained_variance=pca.explained_variance_ratio_.tolist(),loadings=pca.components_.tolist(),scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),coordinate_min=lo.tolist(),coordinate_max=hi.tolist(),example_episodes=sample,synthetic=all(k.startswith('synthetic') for k in corpora),seconds=round(time.time()-started,3),source_database_bytes=source.stat().st_size,pairs={k:[[a,b,n] for (a,b),n in sorted(v.items(),key=lambda x:-x[1])] for k,v in pairs.items()},point_columns=['episode_id','pc1','pc2','corpus_index','turns','speakers','switch_rate','mean_target_span','motif_flags','eligible_edges','nonadjacent_edges','known_action_fraction'],motif_flags=dict(group=1,nonadjacent=2,clarification=4,branching=8,targets_available=16))
    for k,v in [('summary',summary),('points',points)]:db.execute('INSERT INTO meta VALUES (?,?)',(k,json.dumps(v,separators=(',',':'))))
    db.executescript('CREATE INDEX atlas_corpus ON atlas(corpus);');db.commit();db.close();src.close();temp.replace(dest)
    dest.with_suffix('.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:summary[k] for k in ['episodes','source_records','seconds','explained_variance']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,default=Path.home()/'Library/CloudStorage/Dropbox/Git/data/dna_2026/processed/atlas.sqlite');p.add_argument('--output',type=Path);a=p.parse_args();build(a.database,a.output or a.database.with_name('atlas_map.sqlite'))
