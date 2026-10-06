# syntax=docker/dockerfile:1
# Multi-stage production Dockerfile for Scouts BSA Merit Badge Counselor Workbench

FROM python:3.11-slim AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -e .

FROM python:3.11-slim AS runtime

# Create non-root user for container security
RUN groupadd --gid 10001 scoutsagent && \
    useradd --uid 10001 --gid scoutsagent --shell /bin/bash --create-home scoutsagent

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8085

COPY --from=builder /wheels /wheels
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY ui/ ./ui/
COPY assets/ ./assets/

RUN pip install --no-cache-dir --no-index --find-links=/wheels -e . && \
    rm -rf /wheels && \
    mkdir -p /app/deliverables /app/assets/diagrams /app/assets/custom_logos && \
    chown -R scoutsagent:scoutsagent /app

USER scoutsagent

EXPOSE 8085

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8085/health', timeout=3)" || exit 1

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8085"]
