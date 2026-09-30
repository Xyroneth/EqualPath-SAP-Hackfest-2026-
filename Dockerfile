# EQUALPATH: single container (FastAPI serves the built React/UI5 frontend)
FROM node:22-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build --outDir /out --emptyOutDir

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SQLITE_PATH=/data/equalpath.db CHECKPOINT_PATH=/data/equalpath_checkpoints.db
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /out ./app/static
RUN mkdir -p /data && useradd -m equalpath && chown -R equalpath /data /app
USER equalpath
EXPOSE 8000
# Cloud hosts (Render, Railway, Cloud Run...) pass the port in $PORT; locally it is 8000.
HEALTHCHECK CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'))"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
