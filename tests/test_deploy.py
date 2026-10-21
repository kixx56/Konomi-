"""Deployment / proxy / provider regression checks. All provider calls are mocks."""
import json
import os
import sqlite3
from pathlib import Path
import httpx
import pytest
from fastapi import HTTPException
from test_api import client, auth, HEAD, PASSWORD
import main
import store
import runtime
import serve
import ai_provider

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('route',['/admin','/admin/','/admin.html'])
def test_admin_aliases_are_real_html(client,route):
    r=client.get(route,follow_redirects=False)
    assert r.status_code==200 and 'text/html' in r.headers['content-type']
    assert 'id="loginForm"' in r.text
    assert r.headers['cache-control']=='no-store'

@pytest.mark.parametrize('asset',['admin.js','shared.js','admin.html','app.js','style.css'])
def test_admin_assets_are_in_release(client,asset):
    r=client.get('/'+asset)
    assert r.status_code==200 and r.headers['cache-control'] in ('no-cache','no-store')

def test_ready_is_local_and_independent_of_provider(client):
    r=client.get('/api/ready')
    assert r.status_code==200 and r.json()['database']=='ok'
    assert r.json()['frontend']=='complete'
    assert client.get('/api/admin/diagnostics').status_code==401
    auth(client)
    d=client.get('/api/admin/diagnostics').json()
    assert d['frontend_complete'] and 'gemini_key' not in d

@pytest.mark.parametrize('value,expected',[('8000',8000),(' 18765 ',18765),('65535',65535)])
def test_dynamic_port_parser(value,expected):assert serve.port_value(value)==expected

@pytest.mark.parametrize('value',['$PORT','${PORT:-8000}','0','65536','abc','8.0','-1'])
def test_invalid_ports_fail_early(value):
    with pytest.raises(ValueError,match='PORT must be'):serve.port_value(value)


def test_root_build_configuration():
    cfg=json.loads((ROOT/'railway.json').read_text())
    assert cfg['build']['builder']=='DOCKERFILE'
    assert cfg['build']['dockerfilePath']=='Dockerfile'
    assert cfg['deploy']['healthcheckPath']=='/api/ready'
    assert '$PORT' not in cfg['deploy']['startCommand']
    docker=(ROOT/'Dockerfile').read_text()
    assert not any(l.strip().startswith('VOLUME ') for l in docker.splitlines())
    assert '/opt/konomi' in docker and 'validate_assets' in docker


def test_missing_admin_fails_release_preflight(tmp_path,monkeypatch):
    monkeypatch.setenv('KONOMI_FRONTEND_DIR',str(tmp_path))
    (tmp_path/'index.html').write_text('hello')
    with pytest.raises(RuntimeError,match='admin.html'):runtime.validate_assets()


def test_railway_requires_persistent_storage(monkeypatch,tmp_path):
    monkeypatch.setenv('RAILWAY_PROJECT_ID','test-railway-project')
    monkeypatch.delenv('RAILWAY_VOLUME_MOUNT_PATH',raising=False)
    monkeypatch.delenv('KONOMI_DATA_DIR',raising=False)
    monkeypatch.delenv('KONOMI_ALLOW_EPHEMERAL',raising=False)
    with pytest.raises(RuntimeError,match='persistent Volume'):runtime.validate_data_location()
    monkeypatch.setenv('RAILWAY_VOLUME_MOUNT_PATH',str(tmp_path))
    assert runtime.data_dir()==tmp_path
    assert runtime.validate_data_location()==tmp_path
    monkeypatch.setenv('KONOMI_DATA_DIR',str(tmp_path.parent/'outside'))
    with pytest.raises(RuntimeError,match='outside'):runtime.validate_data_location()


def test_code_or_public_directory_cannot_be_data(monkeypatch):
    for value in [str(runtime.ROOT),str(runtime.ROOT/'backend'),str(runtime.frontend_dir()),str(runtime.frontend_dir()/'private'),'/']:
        monkeypatch.setenv('KONOMI_DATA_DIR',value)
        with pytest.raises(RuntimeError,match='Unsafe data mount'):runtime.validate_data_location()


def test_production_first_boot_requires_explicit_password(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.delenv('ADMIN_PASSWORD',raising=False)
    with pytest.raises(RuntimeError,match='ADMIN_PASSWORD'):store.init()


def test_missing_encryption_key_is_not_silently_replaced(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    (tmp_path/'konomi.db').touch()
    with pytest.raises(RuntimeError,match='Encryption key is missing'):store.init()


def test_proxy_https_login_and_csrf(client,monkeypatch):
    # Host is the public Railway domain; scheme was normalized by the trusted ingress.
    client.base_url=httpx.URL('https://demo.up.railway.app')
    monkeypatch.setenv('APP_ENV','production')
    r=client.post('/api/admin/login',json={'username':'admin','password':PASSWORD},headers={**HEAD,'Origin':'https://demo.up.railway.app'})
    assert r.status_code==200
    assert 'secure' in r.headers['set-cookie'].lower()
    assert client.get('/api/admin/me').status_code==200
    r=client.put('/api/admin/settings',json={'venue':'Demo','model':'auto'},headers={**HEAD,'Origin':'https://other-domain.test'})
    assert r.status_code==403


def configure_key(client):
    auth(client)
    client.put('/api/admin/settings',json={'venue':'Demo','model':'auto','gemini_key':'fake-secret-for-provider-tests'},headers=HEAD)
    ai_provider.clear_cache()


def test_models_pagination_filtering_and_header(client,monkeypatch):
    configure_key(client);calls=[]
    async def fake_get(url,**kwargs):
        calls.append(kwargs)
        assert kwargs['headers']['x-goog-api-key']=='fake-secret-for-provider-tests'
        assert 'key=' not in str(url)
        if kwargs['params'].get('pageToken')=='next':
            return httpx.Response(200,json={'models':[{'name':'models/gemini-test-flash','supportedGenerationMethods':['generateContent'],'displayName':'Test flash'}]})
        return httpx.Response(200,json={'models':[{'name':'models/embedding-001','supportedGenerationMethods':['embedContent']},{'name':'models/gemini-image-preview','supportedGenerationMethods':['generateContent']}],'nextPageToken':'next'})
    monkeypatch.setattr(client.app.state.http,'get',fake_get)
    r=client.get('/api/admin/ai/models?refresh=true')
    assert r.status_code==200 and [m['id'] for m in r.json()['models']]==['gemini-test-flash']
    assert len(calls)==2


def test_available_model_is_resolved_and_generation_is_async(client,monkeypatch):
    configure_key(client)
    async def fake_get(*args,**kwargs):return httpx.Response(200,json={'models':[{'name':'models/gemini-99.0-flash','supportedGenerationMethods':['generateContent']}]})
    async def fake_post(url,**kwargs):
        assert url.endswith('/models/gemini-99.0-flash:generateContent')
        assert kwargs['headers']['x-goog-api-key']=='fake-secret-for-provider-tests'
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]})
    monkeypatch.setattr(client.app.state.http,'get',fake_get);monkeypatch.setattr(client.app.state.http,'post',fake_post)
    r=client.post('/api/admin/ai/test',headers=HEAD)
    assert r.status_code==200 and r.json()['model']=='gemini-99.0-flash'


@pytest.mark.parametrize('http_code,kind,message',[(404,'model_not_found','not found'),(403,'authorization','permission denied'),(429,'quota','quota'),(503,'unavailable','unavailable'),(400,'leaked_key','Your API key was reported as leaked. fake-secret-for-provider-tests')])
def test_provider_error_diagnostics_never_echo_keys(client,monkeypatch,http_code,kind,message):
    configure_key(client)
    async def fail(*args,**kwargs):return httpx.Response(http_code,json={'error':{'message':message}})
    monkeypatch.setattr(client.app.state.http,'get',fail)
    r=client.get('/api/admin/ai/models?refresh=true')
    assert r.status_code in (502,503)
    assert 'fake-secret-for-provider-tests' not in r.text
    d=client.get('/api/admin/diagnostics').json()
    assert d['ai']['last_error']['kind']==kind


def test_models_diagnostics_are_private(client):
    assert client.get('/api/admin/ai/models').status_code==401
    assert client.get('/api/admin/diagnostics').status_code==401
