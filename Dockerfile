FROM python:3.12-slim AS requirements-builder

WORKDIR /app

# Copy dependency manifests only (layer cache)
COPY pyproject.toml poetry.lock* ./

# Use a throwaway Poetry environment to export runtime requirements, then
# install only those runtime packages into the venv that gets copied forward.
RUN python -m venv /tmp/poetry-venv \
    && . /tmp/poetry-venv/bin/activate \
    && pip install --upgrade pip \
    && pip install poetry poetry-plugin-export \
    && poetry export --without-hashes --only main -f requirements.txt -o /tmp/requirements.txt \
    && python -m venv /venv \
    && . /venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && python -m pip uninstall -y pip \
    && rm -rf /tmp/poetry-venv /tmp/requirements.txt

# ─────────────────────────────────────────────
FROM python:3.12-slim

ARG NEUTARR_VERSION
ENV NEUTARR_VERSION=${NEUTARR_VERSION}

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=requirements-builder /venv /venv

ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

# Copy application code
COPY . /app/
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Create non-root user and config directories
RUN groupadd -r neutarr && useradd -r -g neutarr -u 1000 neutarr \
    && mkdir -p /config/settings /config/stateful /config/user /config/logs \
    && chown -R neutarr:neutarr /config /app \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONPATH=/app

LABEL name="NeutArr" \
      description="Automated missing media hunter and quality upgrader for *arr apps" \
      url="https://github.com/I-am-PUID-0/NeutArr" \
      maintainer="I-am-PUID-0"

EXPOSE 9705

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9705/api/health', timeout=3).read()" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python3", "main.py"]
