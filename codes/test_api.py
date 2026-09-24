"""Contract checks against the bundled sample, without a listening server."""
from pathlib import Path
import hashlib, sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import server

class ApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=server.DB
        server.DB=Path(__file__).resolve().parents[1]/'app/demo.sqlite'
        cls.before=hashlib.sha256(server.DB.read_bytes()).hexdigest()
        cls.client=TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        after=hashlib.sha256(server.DB.read_bytes()).hexdigest()
        cls.client.close();server.DB=cls.original
        if after!=cls.before:raise AssertionError('Read-only demo mutated its database')

    def test_bounds_and_missing_records(self):
        self.assertEqual(self.client.get('/api/conversation',params={'id':'missing'}).status_code,404)
        self.assertEqual(self.client.get('/api/conversations',params={'limit':61}).status_code,422)
        self.assertEqual(self.client.post('/api/match',json={'id':'synthetic:example-1','stop':50}).status_code,422)

    def test_overlay_does_not_rewrite_source(self):
        cid='synthetic:example-1'
        before=self.client.get('/api/conversation',params={'id':cid}).json()
        result=self.client.post('/api/match',json={'id':cid,'stop':6,'overrides':[{'turn':1,'action':'question'}]})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['query']['turns'][1]['action'],'question')
        self.assertEqual(self.client.get('/api/conversation',params={'id':cid}).json(),before)
        self.assertTrue(result.json()['results'])

    def test_untrusted_search_is_literal_and_bounded(self):
        for q in ['" OR * NEAR(', '<script>alert(1)</script>', '']:
            response=self.client.get('/api/conversations',params={'q':q,'limit':2})
            self.assertEqual(response.status_code,200)
            self.assertLessEqual(len(response.json()['results']),2)

    def test_full_atlas_and_pair_drilldown_agree(self):
        data=self.client.get('/api/atlas').json()
        self.assertEqual(data['summary']['episodes'],len(data['points']))
        self.assertEqual(len(data['points']),5)
        pair=self.client.get('/api/atlas/pair',params={'corpus':'synthetic','from':'clarify','to':'answer'})
        self.assertEqual(pair.status_code,200)
        episode=self.client.get('/api/atlas/episode',params={'id':pair.json()['id']}).json()
        source=self.client.get('/api/conversation',params={'id':episode['cid']}).json()
        self.assertTrue(any(source['turns'][e['target']]['action']=='clarify' and source['turns'][e['source']]['action']=='answer' for e in source['edges']))
        point=next(p for p in data['points'] if p[0]==episode['id'])
        self.assertEqual(point[4],episode['stop']-episode['start'])

    def test_chronology_is_absent_from_atlas_pair_census(self):
        data=self.client.get('/api/atlas').json();ci=data['summary']['corpora'].index('synthetic_variants')
        p=next(p for p in data['points'] if p[3]==ci)
        self.assertIsNone(p[7]);self.assertEqual(p[9],0)
        self.assertEqual(data['summary']['pairs']['synthetic_variants'],[])
        self.assertEqual(self.client.get('/api/atlas/pair',params={'corpus':'synthetic_variants','from':'user','to':'assistant'}).status_code,404)

if __name__=='__main__':unittest.main()
