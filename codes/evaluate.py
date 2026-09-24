"""Held-out known-answer graph-motif retrieval and controlled sensitivity tests.

Relevance is exact annotation-graph containment, NOT human semantic relevance.
Training conversations form the pool; each query is a connected 3-turn motif
from a different Molweni test conversation. No model fitting is performed.
"""
from pathlib import Path
import collections, copy, hashlib, itertools, json, os, platform, random, sqlite3, time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from representation import canonical_speakers, features
from retrieval import align

DATA=Path(os.environ.get('DNA_PROCESSED',Path.home()/'Library/CloudStorage/Dropbox/Git/data/dna_2026/processed'))
OUT=Path(__file__).resolve().parents[1]/'results'
SEED=20260923

def motifs(c):
    """Independent exhaustive two-edge, three-node typed motif oracle."""
    es=c['edges'];seen=set()
    for e,f in itertools.combinations(es,2):
        nodes=sorted({e['source'],e['target'],f['source'],f['target']})
        if len(nodes)!=3:continue
        ix={v:k for k,v in enumerate(nodes)}
        ts=[dict(c['turns'][i]) for i in nodes];canonical_speakers(ts)
        ee=[dict(x,source=ix[x['source']],target=ix[x['target']]) for x in (e,f)]
        key=json.dumps(([t['action'] for t in ts],[t['speaker'] for t in ts],sorted((x['source'],x['target'],x['type']) for x in ee)),separators=(',',':'))
        if key in seen:continue
        seen.add(key)
        yield key,dict(id=c['id'],corpus=c['corpus'],turns=ts,edges=ee,original_positions=nodes)

def bootstrap(values,rng):
    x=np.asarray(values,dtype=float)
    draws=rng.choice(x,(2000,len(x)),replace=True).mean(axis=1)
    return dict(mean=float(x.mean()),ci95=[float(v) for v in np.quantile(draws,[.025,.975])])

def text_family_filter(train,test):
    """Keep one representative of near-duplicate conversation families.

    Families share >=4 distinct utterances of >=20 characters and at least
    80% of the smaller qualifying utterance set. Union-find is transitive.
    Test sources in any training family are excluded before query selection.
    """
    corpus=train+test;sets=[];inverted=collections.defaultdict(list)
    parent=list(range(len(corpus)))
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,c in enumerate(corpus):
        ss={' '.join(t['text'].lower().split()) for t in c['turns'] if len(t['text'].strip())>=20};sets.append(ss)
        counts=collections.Counter(j for s in ss for j in inverted[s])
        for j,shared in counts.items():
            if shared>=4 and shared>=.8*min(len(ss),len(sets[j])):parent[root(i)]=root(j)
        for s in ss:inverted[s].append(i)
    retained=[];seen=set()
    for i,c in enumerate(train):
        r=root(i)
        if r not in seen:retained.append(c);seen.add(r)
    excluded=[];clean=[];test_seen=set()
    for i,c in enumerate(test,start=len(train)):
        r=root(i)
        if r in seen or r in test_seen:excluded.append(c['id'])
        else:clean.append(c);test_seen.add(r)
    return retained,clean,excluded

def main():
    OUT.mkdir(exist_ok=True);db=sqlite3.connect(DATA/'atlas.sqlite')
    allc=[json.loads(r[0]) for r in db.execute("SELECT payload FROM conversations WHERE corpus='molweni'")]
    train=[c for c in allc if c['meta']['split']=='train'];test=[c for c in allc if c['meta']['split']=='test']
    train,test,near_excluded=text_family_filter(train,test)
    # Exact normalized text deduplication across splits, independently of labels.
    digest=lambda c:hashlib.sha256(' '.join(t['text'].lower().strip() for t in c['turns']).encode()).hexdigest()
    train_hash={digest(c) for c in train};excluded=[c['id'] for c in test if digest(c) in train_hash];test=[c for c in test if digest(c) not in train_hash]
    inv=collections.defaultdict(set)
    for i,c in enumerate(train):
        for k,_ in motifs(c):inv[k].add(i)
    rng=random.Random(SEED);rng.shuffle(test);queries=[]
    for c in test:
        eligible=[(k,q) for k,q in motifs(c) if 2<=len(inv.get(k,()))<=100]
        if eligible:queries.append(rng.choice(eligible))
        if len(queries)==200:break
    docs=[' '.join(t['text'] for t in c['turns']) for c in train]
    vect=TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=60000,sublinear_tf=True)
    matrix=vect.fit_transform(docs)
    # Use the same structural candidate generation for the two alignment variants.
    scratch=sqlite3.connect(':memory:');scratch.execute('CREATE VIRTUAL TABLE idx USING fts5(tokens)')
    scratch.executemany('INSERT INTO idx(rowid,tokens) VALUES (?,?)',[(i+1,features(c)) for i,c in enumerate(train)])
    rows=[];latencies=[]
    for qi,(key,q) in enumerate(queries):
        positive=inv[key];qtext=' '.join(t['text'] for t in q['turns'])
        lexical=(matrix@vect.transform([qtext]).T).toarray().ravel()
        lexrank=np.argsort(-lexical,kind='stable')[:10].tolist()
        terms=list(dict.fromkeys(features(q).split()));fts=' OR '.join('"'+s+'"' for s in terms)
        t0=time.perf_counter();candidates=[r[0]-1 for r in scratch.execute('SELECT rowid FROM idx WHERE idx MATCH ? ORDER BY rank LIMIT 120',(fts,))]
        rankings={};scores={}
        for mode in ['sequence','graph']:
            ss=[(align(q,train[i],graph=mode=='graph')['score'],i) for i in candidates]
            # Content-independent deterministic tie order; report ties separately in sensitivity tests.
            rankings[mode]=[i for _,i in sorted(ss,key=lambda x:(-x[0],x[1]))[:10]]
        latencies.append((time.perf_counter()-t0)*1000)
        rankings['tfidf']=lexrank
        record=dict(query_id=q['id'],positions=q['original_positions'],motif_key=key,positive_count=len(positive),candidate_hits=len(positive&set(candidates)),candidate_count=len(candidates),metrics={})
        for name,rank in rankings.items():
            relevant=[int(i in positive) for i in rank]
            record['metrics'][name]=dict(p5=sum(relevant[:5])/5,p10=sum(relevant)/10,success10=int(any(relevant)),rr10=next((1/(i+1) for i,v in enumerate(relevant) if v),0))
        rows.append(record)
        if qi%25==0:print('query',qi,flush=True)
    nrng=np.random.default_rng(SEED)
    report=dict(seed=SEED,task='Exact typed three-node motif containment on human annotations; not semantic relevance',train_conversations=len(train),test_conversations=len(test),excluded_test_near_duplicate_families=near_excluded,excluded_test_exact_duplicates=excluded,query_conversations=len(queries),candidate_limit=120,methods={})
    for mode in ['tfidf','sequence','graph']:
        report['methods'][mode]={k:bootstrap([r['metrics'][mode][k] for r in rows],nrng) for k in ['p5','p10','success10','rr10']}
    report['paired_graph_minus_sequence_p5']=bootstrap([r['metrics']['graph']['p5']-r['metrics']['sequence']['p5'] for r in rows],nrng)
    report['candidate_oracle_success']=sum(r['candidate_hits']>0 for r in rows)/len(rows)
    report['candidate_positive_recall']=sum(r['candidate_hits']/r['positive_count'] for r in rows)/len(rows)
    report['latency_two_alignment_variants_ms']={k:float(v) for k,v in zip(['p50','p95'],np.quantile(latencies,[.5,.95]))}
    # Full-text identical controls: reroute an edge without changing text/labels.
    controls=[]
    for c in test:
        rewired=copy.deepcopy(c);changed=False
        for e in rewired['edges']:
            options=[i for i in range(e['source']) if i!=e['target']]
            if options:
                e['target']=rng.choice(options);changed=True;break
        if not changed:continue
        a,b=align(c,c),align(c,rewired)
        controls.append(dict(id=c['id'],graph_margin=a['score']-b['score'],sequence_margin=align(c,c,False)['score']-align(c,rewired,False)['score']))
    report['rewiring_control']=dict(n=len(controls),graph_strict_preference=sum(c['graph_margin']>1e-9 for c in controls)/len(controls),sequence_tie_rate=sum(abs(c['sequence_margin'])<1e-9 for c in controls)/len(controls),note='Representation sensitivity only: text-identical inputs cannot be distinguished by any text-only metric, including ConDynS.')
    report['environment']=dict(python=platform.python_version(),machine=platform.machine(),system=platform.platform())
    (OUT/'retrieval_split.json').write_text(json.dumps({'train_ids':[c['id'] for c in train],'test_ids':[c['id'] for c in test]},indent=2))
    (OUT/'retrieval_metrics.json').write_text(json.dumps(report,indent=2));(OUT/'retrieval_queries.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n');(OUT/'rewiring_controls.jsonl').write_text('\n'.join(json.dumps(r) for r in controls)+'\n')
    ceiling=dict(queries=len(rows),p5=sum(min(5,r['positive_count'])/5 for r in rows)/len(rows),interpretation='Exhaustive exact motif lookup ceiling; relevance is known from source annotations.')
    (OUT/'oracle_ceiling.json').write_text(json.dumps(ceiling,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
