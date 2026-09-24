"""Install the shipped archive into a fresh environment and exercise its API."""
from pathlib import Path
import argparse,hashlib,json,os,socket,subprocess,sys,tempfile,time,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,default=ROOT/'dist/conversational-dna-demo.zip')
    parser.add_argument('--report',type=Path,default=ROOT/'results/package_smoke.json')
    args=parser.parse_args();archive=args.archive.resolve();report=args.report.resolve()
    report.parent.mkdir(parents=True,exist_ok=True)
    parent=Path(tempfile.mkdtemp(prefix='dna-install-check-'));project=parent/'conversational-dna';venv=parent/'venv'
    print('Isolated install directory:',parent,flush=True)
    with zipfile.ZipFile(archive) as z:
        assert all(not p.startswith('/') and '..' not in Path(p).parts for p in z.namelist())
        assert not any('/deprecated/' in p or '/atlas.sqlite' in p for p in z.namelist())
        z.extractall(parent)
    subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
    python=venv/'bin/python';log=report.with_suffix('.install.log').open('w')
    subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(project/'requirements.txt')],check=True,stdout=log,stderr=log)
    subprocess.run([str(python),str(project/'codes/create_demo.py')],check=True,stdout=log,stderr=log)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env=dict(os.environ,DNA_DATABASE=str(project/'app/demo.sqlite'))
    proc=subprocess.Popen([str(python),str(project/'app/server.py'),'--host','127.0.0.1','--port',str(port)],cwd=project,env=env,stdout=log,stderr=log)
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/stats',timeout=2) as r:stats=json.load(r)
                break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Packaged server did not start')
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/match',data=json.dumps(dict(id='synthetic:example-1',stop=6,corpus='synthetic')).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=5) as r:matches=json.load(r)
        assert stats['_build']['synthetic'] is True
        assert len(matches['results'])==3,matches
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/atlas',timeout=5) as r:atlas=json.load(r)
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/atlas/pair?corpus=synthetic&from=clarify&to=answer',timeout=5) as r:pair=json.load(r)
        assert len(atlas['points'])==5 and atlas['summary']['synthetic'] is True
        assert pair['id'] in [p[0] for p in atlas['points']]
        result=dict(archive=archive.name,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),clean_venv_install=True,synthetic_records=sum(v.get('conversations',0) for k,v in stats.items() if not k.startswith('_')),matching_results=len(matches['results']),atlas_points=len(atlas['points']),pair_lookup=True,matching_corpus='synthetic',port_bound_locally=True)
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()
    result['process_stopped']=True
    report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
