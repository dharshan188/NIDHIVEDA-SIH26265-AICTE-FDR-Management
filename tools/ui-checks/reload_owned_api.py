"""Reload only this session's owned API process, preserving secrets in process environment."""
import os,signal,subprocess,sys,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[2]
port,work=sys.argv[1:]
found=[]
for path in Path('/proc').iterdir():
    if not path.name.isdigit():continue
    try:
        cmd=(path/'cmdline').read_bytes().split(b'\0')
        if b'uvicorn' not in cmd or port.encode() not in cmd:continue
        env=dict(v.decode().split('=',1) for v in (path/'environ').read_bytes().split(b'\0') if b'=' in v)
        if env.get('TL_DATABASE_URL')!=f'sqlite:///{root}/.ui-check/{work}/ui.db':continue
        found.append((int(path.name),env))
    except (OSError,ProcessLookupError):pass
assert len(found)==1, f'Expected exactly one owned API process; found {len(found)}'
pid,env=found[0]
print(f'Reloading owned API PID {pid}, port {port}, database {work}; keys preserved in child environment only.',flush=True)
os.kill(pid,signal.SIGTERM)
for _ in range(100):
    if not Path(f'/proc/{pid}').exists():break
    time.sleep(.1)
child=subprocess.Popen([str(root/'.venv/bin/python'),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',port],cwd=root/'backend',env=env)
for _ in range(100):
    try:
        with urllib.request.urlopen(f'http://localhost:{port}/api/health') as r:assert r.status==200
        break
    except Exception:time.sleep(.2)
else:raise RuntimeError('API did not become ready')
if port=='8002':(root/'.ui-check/session7-api-restarting').unlink(missing_ok=True)
print('API ready with current metrics code; no containers restarted.',flush=True)
sys.exit(child.wait())
