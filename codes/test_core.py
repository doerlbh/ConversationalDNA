"""Meaningful invariants: speaker renaming, rewiring, boundaries, unknown edges."""
import copy, unittest
from representation import slice_episode, trusted_edges
from retrieval import align, safe_fts

def example():
    return dict(id='test:1',corpus='test',turns=[dict(id=i,text=str(i),speaker=s,action=a) for i,(s,a) in enumerate(zip(['A','B','C','B'],['question','clarify','comment','answer']))],edges=[dict(source=1,target=0,type='clarify',provenance='human-discourse'),dict(source=3,target=1,type='answer',provenance='human-discourse')])

class Invariants(unittest.TestCase):
    def test_speaker_renaming(self):
        a=example();b=copy.deepcopy(a)
        for t in b['turns']:t['speaker']='renamed-'+t['speaker']
        self.assertAlmostEqual(align(a,a)['score'],align(a,b)['score'])
    def test_target_matters(self):
        a=example();b=copy.deepcopy(a);b['edges'][1]['target']=0
        self.assertGreater(align(a,a)['score'],align(a,b)['score'])
        self.assertEqual(align(a,a,False)['score'],align(a,b,False)['score'])
    def test_boundary(self):
        a=example();ep=slice_episode(a,1,4)
        self.assertEqual(len(ep['external_edges']),1)
        self.assertEqual(ep['edges'][0]['target'],0)
        self.assertEqual(ep['edges'][0]['source'],2)
    def test_chronology_not_semantics(self):
        a=example()
        for e in a['edges']:e['provenance']='chronological'
        self.assertEqual(trusted_edges(a),[])
        self.assertIsNone(align(a,a)['edge_f1'])
    def test_fts_literal(self):
        self.assertEqual(safe_fts('" OR * NEAR (cat)'), '"OR" OR "NEAR" OR "cat"')

if __name__=='__main__':unittest.main()
