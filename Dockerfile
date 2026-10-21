FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0
# Code deliberately lives outside /app; a legacy /app volume cannot hide admin.html.
WORKDIR /opt/konomi
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && groupadd --gid 10001 konomi && useradd --uid 10001 --gid konomi --create-home konomi
COPY backend ./backend
COPY frontend ./frontend
# Fail the BUILD if admin assets were forgotten in git or excluded by .dockerignore.
RUN python -c "import sys; sys.path.insert(0,'backend'); from runtime import validate_assets; validate_assets()"
EXPOSE 8000
# No Docker VOLUME instruction: Railway storage is configured via Railway Volumes.
# Entrypoint prepares runtime volume permissions, drops root, then starts uvicorn.
CMD ["python", "backend/container_entry.py"]
