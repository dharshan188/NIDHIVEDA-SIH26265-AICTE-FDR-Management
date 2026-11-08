"""Scan the source set selected by git ignore rules, without staging or committing."""
from pathlib import Path
import shutil, subprocess
root=Path(__file__).resolve().parents[2]
dest=root/'.ui-check/source-secret-scan'
if dest.exists(): shutil.rmtree(dest)
dest.mkdir()
raw=subprocess.check_output(['git','-C',str(root),'ls-files','-z','--cached','--others','--exclude-standard','--','.'])
count=0
for name in sorted(set(raw.decode().split('\0'))- {''}):
    src=root/name
    if not src.is_file(): continue
    target=dest/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,target); count+=1
print(f'Copied {count} source files selected by git ignore rules; no git stage/commit.',flush=True)
subprocess.run(['docker','run','--rm','-v',f'{dest}:/repo:ro','zricethezav/gitleaks:v8.18.4','detect','--no-git','--source','/repo','--redact','--no-banner'],check=True)
