"""Download versioned research inputs; retain source URLs and SHA256 hashes.

Run: python codes/acquire.py [--data-root PATH]
No credentials are used. Gated sources fail explicitly; no access bypass.
"""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, time, urllib.request, zipfile

DEFAULT = Path.home() / 'Library/CloudStorage/Dropbox/Git/data/dna_2026'
BASE = 'https://zissou.infosci.cornell.edu/convokit/datasets/'
SOURCES = {name: BASE + name + '/' + name + '.zip' for name in [
    'reddit-coarse-discourse-corpus', 'conversations-gone-awry-cmv-corpus',
    'deli-corpus', 'chromium-corpus']}
SOURCES['wildchat-shard-00000.parquet'] = 'https://huggingface.co/datasets/allenai/WildChat-4.8M/resolve/main/data/train-00000-of-00086.parquet'
for split in ['train','dev','test']:
    SOURCES['molweni/'+split+'.json']='https://raw.githubusercontent.com/HIT-SCIR/Molweni/main/DP/'+split+'.json'
SOURCES['molweni/LICENSE.txt']='https://raw.githubusercontent.com/HIT-SCIR/Molweni/main/LICENSE'

def download(name, url, root):
    dst = root / 'raw' / (name if Path(name).suffix else name + '.zip')
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        partial = dst.with_suffix(dst.suffix + '.partial')
        with urllib.request.urlopen(url, timeout=120) as src, partial.open('wb') as out:
            while chunk := src.read(1024 * 1024):
                out.write(chunk)
        partial.rename(dst)
    digest = hashlib.file_digest(dst.open('rb'), 'sha256').hexdigest()
    if dst.suffix == '.zip':
        target = root / 'raw' / name
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(dst) as z:
            for member in z.infolist():
                path = (target / member.filename).resolve()
                if not path.is_relative_to(target.resolve()):
                    raise ValueError('Unsafe archive member')
                if not path.exists():
                    z.extract(member, target)
    record = dict(name=name, url=url, path=str(dst), bytes=dst.stat().st_size,
                  sha256=digest, retrieved_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    print(json.dumps(record), flush=True)
    return record

def main():
    p = argparse.ArgumentParser(); p.add_argument('--data-root', type=Path, default=DEFAULT)
    args = p.parse_args()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        jobs = [pool.submit(download, n, u, args.data_root) for n, u in SOURCES.items()]
        records = [job.result() for job in jobs]
    out = args.data_root / 'sources' / 'acquisition.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, indent=2))

if __name__ == '__main__': main()
