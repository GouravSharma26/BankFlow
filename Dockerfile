# BankFlow Read-Only Reporting API — Production Container
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -e ".[api]"

# Final runtime stage
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime PostgreSQL client library
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install editable package pointing to copied source
RUN pip install --no-cache-dir --no-deps -e ".[api]"

# Security: non-root user
RUN groupadd -g 10001 bankflow && \
    useradd -u 10001 -g bankflow -s /bin/bash -m bankflow && \
    chown -R bankflow:bankflow /app

USER bankflow

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BANKFLOW_API_HOST=0.0.0.0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT:-${BANKFLOW_API_PORT:-8000}}/api/v1/health" || exit 1

ENTRYPOINT ["bankflow", "serve", "--host", "0.0.0.0"]
