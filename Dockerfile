FROM python:3.12-slim AS requirements-builder

# Build deps for bcrypt/cffi compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests only (layer cache)
COPY pyproject.toml poetry.lock* ./

# Create venv, pre-pin cffi<2.0 + cryptography before Poetry so pip resolver
# never pulls cffi 2.x (breaking changes / potential segfaults), then install deps.
RUN python -m venv /venv \
    && . /venv/bin/activate \
    && pip install --upgrade pip \
    && pip install "cffi>=1.16,<2.0" "cryptography>=42.0,<47.0" \
    && pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root --only main

# ─────────────────────────────────────────────
FROM python:3.12-slim

ARG NEUTARR_VERSION
ENV NEUTARR_VERSION=${NEUTARR_VERSION}

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=requirements-builder /venv /venv

ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

# Copy application code
COPY . /app/

# Create non-root user and config directories
RUN groupadd -r neutarr && useradd -r -g neutarr -u 1000 neutarr \
    && mkdir -p /config/settings /config/stateful /config/user /config/logs \
    && chown -R neutarr:neutarr /config /app

ENV PYTHONPATH=/app

LABEL name="NeutArr" \
      description="Automated missing media hunter and quality upgrader for *arr apps" \
      url="https://github.com/I-am-PUID-0/NeutArr" \
      maintainer="I-am-PUID-0"

EXPOSE 9705

USER neutarr

CMD ["python3", "main.py"]
