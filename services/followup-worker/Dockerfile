# Cloud Run JOB image (runs to completion, not an HTTP server). Build
# context MUST be the repo root (aegis/):
#   docker build -f services/followup-worker/Dockerfile -t aegis-followup-worker .
FROM python:3.12-slim

WORKDIR /app

COPY shared ./shared
COPY services/followup-worker ./followup-worker

RUN pip install --no-cache-dir ./shared \
    && sed -i '/^-e /d' followup-worker/requirements.txt \
    && pip install --no-cache-dir -r followup-worker/requirements.txt

WORKDIR /app/followup-worker

CMD ["python", "main.py"]
