# syntax=docker/dockerfile:1
# Production Dockerfile for Scouts BSA Merit Badge Counselor Workbench (Cloud Run / Kubernetes)

FROM python:3.11-slim

# Install poppler-utils (pdftoppm) for rendering official BSA Merit Badge Pamphlet PDF covers & figures,
# and create non-root user for container security
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 10001 scoutsagent && \
    useradd --uid 10001 --gid scoutsagent --shell /bin/bash --create-home scoutsagent

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    PORT=8085

# Install package dependencies first for layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Copy runtime application assets, prompts, configs, UI, and evaluation gate scripts
COPY scripts/ ./scripts/
COPY tests/data/ ./tests/data/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY ui/ ./ui/
COPY assets/ ./assets/

RUN mkdir -p /app/.cache /app/deliverables /app/assets/diagrams /app/assets/custom_logos /app/tests/data /tmp/matplotlib && \
    chown -R scoutsagent:scoutsagent /app /tmp/matplotlib

USER scoutsagent

EXPOSE 8085

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import os, urllib.request; port = os.environ.get('PORT', '8085'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8085}"]
