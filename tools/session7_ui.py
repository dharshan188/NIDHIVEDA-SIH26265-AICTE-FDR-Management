"""Serial browser checks prevent OTP races; never changes container state."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env={**os.environ,'TL_UI_INSTITUTION_MFA':'totp','UI_BASE':'http://localhost:5175','UI_LOGIN_BASE':'http://localhost:5173', 'TL_UI_DB':str(root/'.ui-check/session7-final/ui.db'),'TL_UI_EVIDENCE':str(root/'docs/verification/session7')+'/'}
checks=[('76-axe-panels-dark-complete',['node','tools/ui-checks/axe_panels.mjs','--theme','dark']),('68-axe-light-complete',['node','tools/ui-checks/axe.mjs','--theme','light']),('69-axe-dark-complete',['node','tools/ui-checks/axe.mjs','--theme','dark']),('70-pdf-labels-final',['node','tools/ui-checks/pdf_check.mjs']),('71-nudge-sql-final',['node','tools/ui-checks/live_data.mjs']),('72-refreshed-screenshots',['node','tools/ui-checks/retake_final.mjs'])]
for label,args in checks:
    child={**env,'AXE_RESULT':str(root/f'docs/verification/session7/{label}.json')}
    r=subprocess.run([sys.executable,str(root/'tools/session7_run.py'),label,*args],cwd=root,env=child)
    if r.returncode: sys.exit(r.returncode)
