from collections import Counter
import json
from pathlib import Path
items=json.loads(Path('docs/verification/session7/gitleaks-whole.json').read_text())
def group(p):
    p=p.removeprefix('/repo/').removeprefix('repo/')
    if p.startswith('.ui-check/'): return '.ui-check/ (ignored verification environments/test certificates)'
    if p.startswith('.venv'): return '.venv*/ (ignored Python dependencies/test vectors)'
    if p.startswith('.python/'): return '.python/ (ignored standalone Python installation)'
    if p.startswith('backend/devcerts/'): return 'backend/devcerts/ (ignored development DSC keys)'
    if p.startswith('backend/.dev-'): return 'backend/.dev-* (ignored local development credentials)'
    return p
print('Whole-directory findings:',len(items))
for p,n in Counter(group(i['File']) for i in items).most_common(): print(n,p)
print('445 source files selected by git ignore rules: no leaks (39-source-secret-scan.txt).')
print('Whole-directory scan is NOT clean; retained ignored local secrets and third-party vectors are not source-code leaks. No commit performed.')
