"""Populate manuscript tables/macros directly from measured artifacts."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1];RES=ROOT/'results';TEX=ROOT/'latex'
def main():
    m=json.loads((RES/'retrieval_metrics.json').read_text());d=json.loads((RES/'dense_metrics.json').read_text());b=json.loads((RES/'api_benchmark.json').read_text());s=b['corpus_stats']
    macros={'QueryCount':m['query_conversations'],'PoolCount':f"{m['train_conversations']:,}",'TestFamilies':m['test_conversations'],
     'GraphPFive':f"{100*m['methods']['graph']['p5']['mean']:.1f}",'SequencePFive':f"{100*m['methods']['sequence']['p5']['mean']:.1f}",
     'PairedGain':f"{100*m['paired_graph_minus_sequence_p5']['mean']:.1f}",'GainLow':f"{100*m['paired_graph_minus_sequence_p5']['ci95'][0]:.1f}",'GainHigh':f"{100*m['paired_graph_minus_sequence_p5']['ci95'][1]:.1f}",
     'SearchMedian':f"{b['search_ms']['p50']:.0f}",'SearchTail':f"{b['search_ms']['p95']:.0f}",'AlignMedian':f"{b['alignment_ms']['p50']:.0f}",'AlignTail':f"{b['alignment_ms']['p95']:.0f}",
     'CandidateSuccess':f"{100*m['candidate_oracle_success']:.1f}",'CandidateRecall':f"{100*m['candidate_positive_recall']:.1f}",'ControlCount':m['rewiring_control']['n']}
    (TEX/'numbers.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+str(v)+'}' for k,v in macros.items())+'\n')
    names={'molweni':'Molweni','reddit':'Reddit discourse','cmv':'CGA--CMV','deli':'DeliData','wildchat':'WildChat shard','prism':'PRISM','dailydialog':'DailyDialog train','chromium':'Chromium'}
    lines=[]
    for k,name in names.items():
        v=s[k];lines.append(f"{name} & {v['conversations']:,} & {v['turns']:,} & {v['episodes']:,} \\\\")
    (TEX/'corpus_rows.tex').write_text('\\newcommand{\\corpusRows}{%\n'+'\n'.join(lines)+'\n}\n')
    lines=[]
    for key,name in [('tfidf','TF--IDF (text)'),('dense','MiniLM (text)'),('sequence','Sequence + speaker'),('graph','+ target correspondence')]:
        vals=d['metrics'] if key=='dense' else m['methods'][key]
        lines.append(name+' & '+' & '.join(f"{100*vals[a]['mean']:.1f}" for a in ['p5','p10','success10'])+' \\\\')
    (TEX/'retrieval_rows.tex').write_text('\\newcommand{\\retrievalRows}{%\n'+'\n'.join(lines)+'\n}\n')
    bib='\n'.join(p.read_text() for p in sorted((ROOT/'literature').glob('*.bib')))+'\n'+(TEX/'additional.bib').read_text()
    (TEX/'references.bib').write_text(bib)
    keys=re.findall(r'@\w+\{([^,]+)',bib);print('Bibliography keys:',keys)
if __name__=='__main__':main()
