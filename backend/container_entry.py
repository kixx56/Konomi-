"""Prepare the runtime-mounted private data directory, then drop root privileges.
Application code is in /opt/konomi so an old /app volume cannot mask the frontend.
"""
import os
import sys
from pathlib import Path
from runtime import validate_assets, validate_data_location

def main():
    validate_assets()
    if not os.getenv('KONOMI_DATA_DIR') and not os.getenv('RAILWAY_VOLUME_MOUNT_PATH'):
        os.environ['KONOMI_DATA_DIR']='/data'
    data=validate_data_location()
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    if hasattr(os,'geteuid') and os.geteuid()==0:
        uid,gid=10001,10001
        os.chown(data,uid,gid)
        os.chmod(data,0o700)
        for name in ('konomi.db','konomi.db-wal','konomi.db-shm','encryption.key'):
            path=data/name
            if path.is_symlink():raise RuntimeError('Symlinks are not allowed for private database files')
            if path.exists():
                os.chown(path,uid,gid);os.chmod(path,0o600)
        os.setgroups([]);os.setgid(gid);os.setuid(uid)
    if not os.access(data,os.R_OK|os.W_OK|os.X_OK):raise RuntimeError('Data volume is not writable by the application user')
    os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name('serve.py'))])

if __name__=='__main__':
    try:main()
    except (RuntimeError,PermissionError) as exc:
        print('Konomi container error: '+str(exc),file=sys.stderr);sys.exit(1)
