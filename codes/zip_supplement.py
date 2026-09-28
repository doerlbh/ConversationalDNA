"""Zip this repository, excluding local build/data files."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
skip={'.git','.venv','venv','__pycache__','.pytest_cache','deprecated','data','raw','qa','github-ready'}
suffixes=('.pyc','.aux','.log','.out','.blg','.bbl','.fls','.fdb_latexmk','.synctex.gz','.zip')
files=[p for p in sorted(root.rglob('*')) if p.is_file()
       and not p.is_symlink()
       and not any(part in skip for part in p.relative_to(root).parts)
       and p.name not in {'.DS_Store','SHA256SUMS'}
       and not p.name.startswith('.env')
       and not p.name.endswith(suffixes)
       and (p.suffix!='.sqlite' or p.relative_to(root).as_posix() in {'app/demo.sqlite','app/demo_map.sqlite'})]
out=root.parent/'conversational-dna-github-supplement.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,'conversational-dna/'+p.relative_to(root).as_posix())
print(f'{out} ({out.stat().st_size:,} bytes)')
