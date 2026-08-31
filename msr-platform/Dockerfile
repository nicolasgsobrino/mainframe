# Imagen única de la plataforma MSR: el backend FastAPI sirve la SPA compilada.
#
# Contexto de build: msr-platform/
#   docker build -t msr-platform:dev msr-platform
#
# La imagen NO contiene credenciales AWS. En ECS Fargate boto3 obtiene
# credenciales temporales del Task Role a través del endpoint de metadatos del
# contenedor (AWS_CONTAINER_CREDENTIALS_RELATIVE_URI, inyectado por el agente):
# no hay access keys, ni session tokens, ni perfiles, ni `aws login`.
#
# El mismo artefacto sirve para dos usos:
#   - servicio:  uvicorn app.main:app            (CMD por defecto)
#   - hook:      python -m app.lab_hook [--confirm]  (task de release puntual)

# --- 1) Build de la SPA -----------------------------------------------------
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2) Runtime del backend -------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/policy ./policy
COPY backend/pyproject.toml ./
# `app.main` monta `backend/static` cuando existe: la SPA se sirve desde el mismo
# origen que la API, así que el frontend no necesita CORS ni un host aparte.
COPY --from=frontend /build/dist ./static

# SQLite persiste los jobs y el lock de reconciliación. En Fargate el directorio
# vive en el volumen efímero de la task: cada revisión arranca con jobs limpios y
# el estado autoritativo del laboratorio se redescubre desde AWS por tags.
RUN mkdir -p /app/data && useradd --uid 10001 --create-home --shell /usr/sbin/nologin msr \
    && chown -R msr:msr /app/data
ENV MSR_JOBS_DB_PATH=/app/data/msr_jobs.db
USER 10001

EXPOSE 8080

# Health check dentro del contenedor: sin dependencias extra (no hay curl).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
