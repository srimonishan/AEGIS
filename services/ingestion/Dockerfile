# Build context MUST be the repo root (aegis/), not this directory, so we
# can COPY the shared package in. See infra/README or the deploy script:
#   docker build -f services/ingestion/Dockerfile -t aegis-ingestion .
FROM python:3.12-slim

WORKDIR /app

COPY shared ./shared
COPY services/ingestion ./ingestion

# Install the shared package first, then strip its editable-path line out
# of requirements.txt before installing the rest -- that line's relative
# path (`-e ../../shared`) only resolves in the monorepo checkout, not
# from this image's /app layout.
RUN pip install --no-cache-dir ./shared \
    && sed -i '/^-e /d' ingestion/requirements.txt \
    && pip install --no-cache-dir -r ingestion/requirements.txt

WORKDIR /app/ingestion

ENV PORT=8080
EXPOSE 8080

# Cloud Run sets $PORT; uvicorn must bind to it.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
