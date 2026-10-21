"""Environment decisions shared by local launch, containers and the API."""
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
REQUIRED_ASSETS=('index.html','admin.html','app.js','admin.js','shared.js','style.css','import-template.csv', 'service-admin.js', 'service-guest.js')

def railway():
    return bool(os.getenv('RAILWAY_PROJECT_ID') or os.getenv('RAILWAY_SERVICE_ID') or os.getenv('RAILWAY_ENVIRONMENT_ID'))

def production():
    return railway() or os.getenv('APP_ENV','').lower() in ('production','prod')

def frontend_dir():
    return Path(os.getenv('KONOMI_FRONTEND_DIR') or str(ROOT/'frontend')).resolve()

def data_dir():
    # Railway injects the actual attached volume mount path at runtime, not build time.
    return Path(os.getenv('KONOMI_DATA_DIR') or os.getenv('RAILWAY_VOLUME_MOUNT_PATH') or str(ROOT/'backend/data')).resolve()

def validate_assets():
    front=frontend_dir()
    missing=[name for name in REQUIRED_ASSETS if not (front/name).is_file()]
    missing += ['backend/'+name for name in ('agent_contract.py','local_agent.py','sommelier.py','dining.py','ai_provider.py') if not (ROOT/'backend'/name).is_file()]
    if missing:
        raise RuntimeError('Release is incomplete: frontend assets missing: '+', '.join(missing)+'. Commit every frontend file and rebuild. Never mount a volume over application code.')
    if not (ROOT/'backend/assets/DejaVuSans.ttf').is_file():
        raise RuntimeError('Print font is missing. Include backend/assets/DejaVuSans.ttf in the release.')
    return front

def validate_data_location():
    data=data_dir()
    protected=(ROOT,ROOT/'backend',frontend_dir())
    if data==Path('/') or any(data==p or data in p.parents for p in protected) or data==frontend_dir() or frontend_dir() in data.parents:
        raise RuntimeError('Unsafe data mount. Use /data, never the project root or frontend directory.')
    # A legacy /app mount is usable because this release keeps code under /opt/konomi.
    # New deployments should always use /data.
    if railway() and not os.getenv('RAILWAY_VOLUME_MOUNT_PATH') and os.getenv('KONOMI_ALLOW_EPHEMERAL','false').lower()!='true':
        raise RuntimeError('Railway: attach a persistent Volume at /data before deploying. Without a Volume admin/menu/AI keys would be lost. KONOMI_ALLOW_EPHEMERAL=true explicitly allows a disposable demo.')
    if railway() and os.getenv('RAILWAY_VOLUME_MOUNT_PATH') and os.getenv('KONOMI_DATA_DIR'):
        mount=Path(os.environ['RAILWAY_VOLUME_MOUNT_PATH']).resolve()
        if data!=mount and mount not in data.parents:
            raise RuntimeError('KONOMI_DATA_DIR is outside the Railway Volume. Remove it or place it inside RAILWAY_VOLUME_MOUNT_PATH.')
    return data
