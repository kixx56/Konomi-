"""Real process smoke test: Railway env, arbitrary PORT/CWD, login and restart.
Uses a temporary data directory. Does not deploy to Railway or call Gemini.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

def stop(proc):
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)

def run():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='konomi-railway-check-') as temp:
        data=Path(temp)/'volume'
        port=free_port()
        env=os.environ.copy()
        for key in ['KONOMI_DATA_DIR','KONOMI_FRONTEND_DIR','GEMINI_API_KEY','KONOMI_ALLOW_EPHEMERAL']:
            env.pop(key,None)
        env.update(PORT=str(port),HOST='0.0.0.0',RAILWAY_PROJECT_ID='simulated-project',RAILWAY_VOLUME_MOUNT_PATH=str(data),ADMIN_PASSWORD='Only-for-local-boot-test-123',COOKIE_SECURE='false')
        for stage in range(2):
            if stage==1:env['ADMIN_PASSWORD']='Changed-env-must-not-reset-existing-admin-123'
            with open(Path(temp)/f'boot-{stage}.log','w+') as logfile:
                proc=subprocess.Popen([sys.executable,str(ROOT/'backend/serve.py')],cwd=temp,env=env,stdout=logfile,stderr=logfile)
                try:
                    base=f'http://127.0.0.1:{port}'
                    with httpx.Client(base_url=base,timeout=3) as client:
                        for _ in range(120):
                            if proc.poll() is not None:
                                logfile.seek(0);raise AssertionError('Server failed: '+logfile.read())
                            try:
                                if client.get('/api/ready').status_code==200:break
                            except httpx.HTTPError:pass
                            time.sleep(.1)
                        else:raise AssertionError('Readiness timeout')
                        for route in ['/','/admin','/admin/','/admin.html','/admin.js','/shared.js']:
                            assert client.get(route).status_code==200,route
                        res=client.post('/api/admin/login',headers={'X-Konomi-Admin':'1'},json={'username':'admin','password':'Only-for-local-boot-test-123'})
                        assert res.status_code==200,res.text
                        assert client.get('/api/admin/me').status_code==200
                        if stage==0:
                            dish={'name':'Persisted smoke-test dish','category':'main','price':42,'status':'draft'}
                            assert client.post('/api/admin/menu',headers={'X-Konomi-Admin':'1'},json=dish).status_code==200
                            checks.append('Process starts from unrelated CWD, binds dynamic PORT and serves all admin URLs')
                        else:
                            items=client.get('/api/admin/menu').json()['dishes']
                            assert any(d['name']=='Persisted smoke-test dish' for d in items)
                            checks.append('Restart preserves database, encryption key, admin password and menu changes')
                finally:stop(proc)
        assert (data/'encryption.key').exists() and (data/'konomi.db').exists()
    print(json.dumps({'checks':checks,'status':'passed'},ensure_ascii=False,indent=2))

if __name__=='__main__':run()
