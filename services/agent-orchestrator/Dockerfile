# Build context MUST be the repo root (aegis/):
#   docker build -f services/agent-orchestrator/Dockerfile -t aegis-orchestrator .
FROM python:3.12-slim

WORKDIR /app

COPY shared ./shared
COPY services/agent-orchestrator ./orchestrator

RUN pip install --no-cache-dir ./shared \
    && sed -i '/^-e /d' orchestrator/requirements.txt \
    && pip install --no-cache-dir -r orchestrator/requirements.txt

WORKDIR /app/orchestrator

ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
