"""Verify scientific descriptor semantics independently of the saved sidecar."""
import unittest
from build_atlas import describe,FIELDS
from representation import slice_episode

class AtlasDescriptors(unittest.TestCase):
    def test_roles_are_unknown_actions_and_chronology_is_not_a_target(self):
        ep={'turns':[dict(speaker='S1',action='user',text='How are you?'),dict(speaker='S2',action='assistant',text='I am well.')], 'edges':[dict(source=1,target=0,type='chronological',provenance='chronological')]}
        f,m,p=describe(ep)
        self.assertEqual(m['known'],0)
        self.assertIsNone(m['reach']);self.assertEqual(m['edges'],0);self.assertFalse(p)
        self.assertEqual(dict(zip(FIELDS,f))['speaker_switching'],1)

    def test_pair_direction_and_nonadjacent_span(self):
        ep={'turns':[dict(speaker='S1',action='clarify',text='Which one?'),dict(speaker='S2',action='comment',text='Another branch.'),dict(speaker='S3',action='answer',text='The second one.')], 'edges':[dict(source=2,target=0,type='QAP',provenance='human-discourse')]}
        f,m,p=describe(ep)
        self.assertEqual(p,{('clarify','answer'):1});self.assertEqual(m['reach'],2)
        self.assertEqual(m['nonadjacent'],1);self.assertEqual(m['flags'],1+2+4+16)
        self.assertEqual(dict(zip(FIELDS,f))['mean_target_span'],1)

    def test_boundary_targets_are_excluded_from_internal_census(self):
        c={'id':'test','corpus':'test','source_id':'test','meta':{},'turns':[dict(speaker='S1',action='clarify',text='Which one?'),dict(speaker='S2',action='comment',text='Another branch.'),dict(speaker='S3',action='answer',text='The second one.')],'edges':[dict(source=2,target=0,type='QAP',provenance='human-discourse')]}
        f,m,p=describe(slice_episode(c,1,3))
        self.assertEqual(m['edges'],0);self.assertIsNone(m['reach']);self.assertFalse(p)

if __name__=='__main__':unittest.main()
