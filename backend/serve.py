"""One start command for Railway/Docker/local hosting: python backend/serve.py.
PORT is parsed in Python; no shell substitution and no literal '$PORT' issue.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
from runtime import railway, validate_assets, validate_data_location

def port_value(value):
    text=str(value).strip()
    if not text.isascii() or not text.isdecimal() or not 1<=int(text)<=65535:
        raise ValueError('PORT must be an integer between 1 and 65535, not a literal $PORT. Clear old Railway Start Command overrides and use python backend/serve.py.')
    return int(text)

def main():
    validate_assets();validate_data_location()
    port=port_value(os.getenv('PORT','8000'))
    host=os.getenv('HOST','0.0.0.0')
    # Trust proxy headers only when behind a trusted ingress. Railway uses an ingress.
    proxies=os.getenv('FORWARDED_ALLOW_IPS','*' if railway() else '127.0.0.1')
    import uvicorn
    uvicorn.run('main:app',host=host,port=port,workers=1,proxy_headers=True,forwarded_allow_ips=proxies,access_log=True)

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,PermissionError) as exc:
        print('Konomi startup error: '+str(exc),file=sys.stderr)
        sys.exit(1)
