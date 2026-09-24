"""Local sequence alignment with explicit graph and speaker correspondence.

The DP proposes monotone alignments; graph reranking is approximate, not an
exact graph edit distance. Defaults are fixed engineering choices, not tuned
on the held-out Molweni test set.
"""
import collections, math, re, sqlite3
from representation import trusted_edges

def local_alignments(query, candidate, top=12):
    a,b=query['turns'],candidate['turns'];n,m=len(a),len(b)
    scores=[[0.]*(m+1) for _ in range(n+1)];back=[[0]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1):
        for j in range(1,m+1):
            x,y=a[i-1]['action'],b[j-1]['action']
            match=.25 if 'unknown' in (x,y) else 2. if x==y else -1.
            vals=(0.,scores[i-1][j-1]+match,scores[i-1][j]-1.,scores[i][j-1]-1.)
            k=max(range(4),key=vals.__getitem__);scores[i][j]=vals[k];back[i][j]=k
    ends=sorted(((scores[i][j],i,j) for i in range(1,n+1) for j in range(1,m+1)),reverse=True)
    seen=set();out=[]
    for value,i,j in ends:
        if value<=0:break
        pairs=[]
        while i and j and scores[i][j]>0:
            k=back[i][j]
            if k==1:pairs.append((i-1,j-1));i-=1;j-=1
            elif k==2:i-=1
            elif k==3:j-=1
            else:break
        pairs=tuple(reversed(pairs))
        if pairs not in seen:
            seen.add(pairs);out.append((value,pairs))
            if len(out)>=top:break
    return out or [(0.,())]

def correspondence(query,candidate,pairs):
    mapping=dict(pairs);reverse={v:k for k,v in pairs}
    qe=trusted_edges(query);ce=trusted_edges(candidate)
    target={(e['source'],e['target'],e['type']) for e in ce}
    matched=[]
    for e in qe:
        i,j=e['source'],e['target']
        if i in mapping and j in mapping and (mapping[i],mapping[j],e['type']) in target:
            matched.append(dict(query_source=i,query_target=j,candidate_source=mapping[i],candidate_target=mapping[j],type=e['type']))
    # Count all query edges and candidate edges whose endpoints are aligned.
    nc=sum(e['source'] in reverse and e['target'] in reverse for e in ce)
    edge_f1=2*len(matched)/(len(qe)+nc) if len(qe)+nc else None
    comparisons=[]
    for x,(i,j) in enumerate(pairs):
        for k,l in pairs[x+1:]:
            comparisons.append((query['turns'][i]['speaker']==query['turns'][k]['speaker']) ==
                               (candidate['turns'][j]['speaker']==candidate['turns'][l]['speaker']))
    speaker=sum(comparisons)/len(comparisons) if comparisons else 0.
    coverage=len(pairs)/max(1,len(query['turns']))
    return dict(edge_f1=edge_f1,speaker=speaker,coverage=coverage,matched_edges=matched,
                query_edges=len(qe),candidate_aligned_edges=nc)

def align(query,candidate,graph=True):
    outputs=[]
    for raw,pairs in local_alignments(query,candidate):
        c=correspondence(query,candidate,pairs)
        sequence=min(1.,raw/(2*max(1,len(query['turns']))))
        # Removing the edge term preserves the relative weights of all others.
        score=(.50*sequence+.15*c['speaker'])/.65 if not graph or c['edge_f1'] is None else .50*sequence+.15*c['speaker']+.35*c['edge_f1']
        outputs.append(dict(score=score,sequence=sequence,pairs=[list(x) for x in pairs],**c))
    return max(outputs,key=lambda o:(o['score'],o['coverage']))

def safe_fts(text):
    # Treat all user input as literal tokens, never as FTS syntax or SQL.
    terms=re.findall(r'[^\W_]+',text,flags=re.UNICODE)[:16]
    return ' OR '.join('"'+x.replace('"','""')+'"' for x in terms)
