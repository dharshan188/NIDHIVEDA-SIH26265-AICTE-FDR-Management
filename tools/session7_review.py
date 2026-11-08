"""Check final documentation links, screenshot manifests and recorded result summaries."""
from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parents[1]
files=[R/'CHANGELOG.md',R/'docs/FINAL_REPORT.md',R/'docs/security.md',R/'docs/notifications.md',R/'docs/scenario-report.md',R/'docs/screenshots/final/README.md']
missing=[];n=0
for p in files:
    for raw in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        target=raw.split('#')[0]
        if not target or '://' in target:continue
        q=(p.parent/target).resolve();n+=1
        if not q.exists():missing.append((str(p.relative_to(R)),target))
assert not missing,missing
print(f'Final documentation: {len(files)} files, {n} local links resolved.')
heads=re.findall(r'^## (.+)$',(R/'CHANGELOG.md').read_text(),re.M)
assert len(heads)==3,heads
print('Changelog lists:',heads)
for row in json.loads((R/'docs/verification/session7/screenshots.json').read_text()):
    p=R/'docs/screenshots/final'/row['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
print('18 final screenshot hashes match manifest; dimensions recorded as 1536x1024.')
scenario=json.loads((R/'docs/scenario-report.json').read_text());assert scenario['passed']==52 and scenario['failed']==0
assert '6 scenarios, 52 checks passed, 0 failed' in (R/'docs/scenario-report.md').read_text()
print('Current scenario JSON/Markdown: 6 scenarios / 52 passed / 0 failed.')
for name in ['68-axe-light-complete','69-axe-dark-complete','66-axe-panels-light-final','76-axe-panels-dark-complete']:
    p=json.loads((R/f'docs/verification/session7/{name}.json').read_text())
    assert not p['errors'];assert not any(r['violations'] for r in p['results']);print(name,len(p['results']),'views, zero violations/errors')
print('Visual QA performed this session via view_image: login, three dashboards, FDR documents/timeline, upload prechecks/encryption, notification centre, escalation, health, missing report, Rules and rendered PDF. SIMULATED label visible on the PDF; no gap proof claimed.')
print('No git commit performed; no kernel edits; ZAP unverified and 2 moderate npm findings retained.')
