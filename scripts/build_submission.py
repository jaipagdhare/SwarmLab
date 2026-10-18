"""Build an allowlisted source archive; never copy .env, exports, or local metadata."""
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOP = {'README.md', '.gitignore', '.env.example', 'compose.yaml', 'pyproject.toml', 'requirements.lock'}
DIRS = ('src', 'static', 'tests', 'scripts', 'docs', 'queries')
SKIP = {'__pycache__', '.pytest_cache', '.git'}


def files():
    result = [ROOT / name for name in TOP]
    for folder in DIRS:
        result.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and not SKIP.intersection(p.parts) and not any(x.endswith('.egg-info') for x in p.parts) and p.suffix != '.pyc')
    return sorted(result)


def check(path):
    if path.suffix in {'.webm','.png','.jpg','.mp4'}:
        return
    text = path.read_text(encoding='utf-8')
    if re.search(r'AIza[0-9A-Za-z_-]{30,}|sk-(?:proj-)?[0-9A-Za-z_-]{24,}',text):
        raise ValueError(f'Potential credential in {path.relative_to(ROOT)}; archive stopped')


if __name__ == '__main__':
    output=ROOT/'outputs'/'submission'/'swarmlab-source.zip'
    output.parent.mkdir(parents=True,exist_ok=True)
    selected=files()
    for path in selected:check(path)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in selected:archive.write(path,Path('graph-hacks')/path.relative_to(ROOT))
    print(f'{len(selected)} allowlisted files packaged: {output}')
