"""Conversational DNA v0.1: evidence-preserving graph representation.

Unknown communicative actions remain unknown. Native annotation inventories
are retained, with a small explicit display mapping (not a learned ontology).
Edges point from the responding turn (source) to its earlier target.
"""
import collections, re

MAPPING = {'QAP':'answer', 'Clarification_question':'clarify', 'Q-Elab':'elaborate',
 'Acknowledgement':'acknowledge', 'Correction':'correct', 'Comment':'comment',
 'Continuation':'continue', 'Elaboration':'elaborate', 'Explanation':'explain',
 'Result':'result', 'Contrast':'contrast', 'Background':'background',
 'Conditional':'condition', 'Narration':'narrate', 'Alternation':'alternative',
 'Parallel':'parallel', 'Probing':'probe', 'Non-probing-deliberation':'propose',
 'Non-deliberation':'social', '1':'inform', '2':'question', '3':'directive', '4':'commissive'}

def canonical_speakers(turns):
    identities = {}
    for t in turns:
        original = str(t['speaker'])
        if original not in identities: identities[original] = f'S{len(identities)+1}'
        t['speaker'] = identities[original]
    return len(identities)

def clean_label(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_') or 'unknown'

def slice_episode(conv, start=0, stop=None):
    stop = min(stop if stop is not None else len(conv['turns']), len(conv['turns']))
    if not 0 <= start < stop: raise ValueError('Invalid episode boundary')
    turns = [dict(t) for t in conv['turns'][start:stop]]
    canonical_speakers(turns)
    edges = [dict(e, source=e['source']-start, target=e['target']-start)
             for e in conv['edges'] if start <= e['source'] < stop and start <= e['target'] < stop]
    external = [dict(e) for e in conv['edges'] if start <= e['source'] < stop and not start <= e['target'] < stop]
    return dict(id=conv['id'], corpus=conv['corpus'], start=start, stop=stop,
                turns=turns, edges=edges, external_edges=external)

def trusted_edges(episode):
    return [e for e in episode['edges'] if e['provenance'] in ('human-discourse','platform-reply','human-link','synthetic-example')]

def features(episode):
    ts = episode['turns']; a = [clean_label(t['action']) for t in ts]
    out = ['a_'+x for x in a]
    out += ['b_'+x+'_'+y for x,y in zip(a,a[1:])]
    out += ['s_'+('same' if x['speaker']==y['speaker'] else 'different') for x,y in zip(ts,ts[1:])]
    for e in trusted_edges(episode):
        s,t = e['source'],e['target']
        lag='near' if abs(s-t)==1 else 'delayed'
        role='same' if ts[s]['speaker']==ts[t]['speaker'] else 'different'
        out.append('e_'+clean_label(e['type'])+'_'+lag+'_'+role)
    return ' '.join(out)

def signature(episode):
    return ' → '.join(t['action'] for t in episode['turns'])

def graph_stats(conv):
    es=trusted_edges(conv); ts=conv['turns']
    return {'turns':len(ts),'speakers':len({t['speaker'] for t in ts}),
            'edges':len(es),'nonadjacent':sum(abs(e['source']-e['target'])>1 for e in es),
            'typed':sum(e['type'] not in ('reply','temporal') for e in es)}
