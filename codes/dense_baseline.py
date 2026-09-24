"""Content-embedding baseline on the exact saved structural retrieval queries."""
from pathlib import Path
import collections, hashlib, json, sqlite3, time
import numpy as np
from fastembed import TextEmbedding
from evaluate import DATA, OUT, SEED, motifs, bootstrap, text_family_filter

def main():
    db=sqlite3.connect(DATA/'atlas.sqlite')
    allc=[json.loads(r[0]) for r in db.execute("SELECT payload FROM conversations WHERE corpus='molweni'")]
    train,test,_=text_family_filter([c for c in allc if c['meta']['split']=='train'],[c for c in allc if c['meta']['split']=='test'])
    queries=[json.loads(s) for s in (OUT/'retrieval_queries.jsonl').read_text().splitlines()]
    byid={c['id']:c for c in test};inv=collections.defaultdict(set)
    for i,c in enumerate(train):
        for k,_ in motifs(c):inv[k].add(i)
    model_name='sentence-transformers/all-MiniLM-L6-v2';model=TextEmbedding(model_name=model_name,cache_dir=str(DATA.parent/'models'),threads=4)
    texts=[' '.join(t['text'] for t in c['turns']) for c in train]
    qtexts=[' '.join(byid[q['query_id']]['turns'][i]['text'] for i in q['positions']) for q in queries]
    t0=time.perf_counter();emb=np.asarray(list(model.embed(texts+qtexts,batch_size=64)));elapsed=time.perf_counter()-t0
    emb=emb/np.maximum(np.linalg.norm(emb,axis=1,keepdims=True),1e-9);np.save(DATA/'molweni_minilm_embeddings.npy',emb)
    rows=[]
    for i,q in enumerate(queries):
        sims=emb[:len(train)]@emb[len(train)+i];rank=np.argsort(-sims,kind='stable')[:10];rel=[int(j in inv[q['motif_key']]) for j in rank]
        rows.append(dict(query_id=q['query_id'],p5=sum(rel[:5])/5,p10=sum(rel)/10,success10=int(any(rel)),rr10=next((1/(i+1) for i,v in enumerate(rel) if v),0)))
    rng=np.random.default_rng(SEED);metrics={k:bootstrap([r[k] for r in rows],rng) for k in ['p5','p10','success10','rr10']}
    result=dict(model=model_name,backend='fastembed ONNX CPU',train_conversations=len(train),queries=len(queries),embedding_seconds=elapsed,metrics=metrics,token_limit=model.model.tokenizer.truncation if hasattr(model.model,'tokenizer') else 'backend default')
    (OUT/'dense_metrics.json').write_text(json.dumps(result,indent=2,default=str));(OUT/'dense_queries.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n');print(json.dumps(result,indent=2,default=str))

if __name__=='__main__':main()
