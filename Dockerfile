# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DOCUVISION_RASTER_DPI=200 \
    DOCUVISION_VLM_BASE_URL=http://localhost:11434/v1 \
    DOCUVISION_VLM_MODEL=llama3.2-vision:latest \
    DOCUVISION_VLM_PROVIDER=ollama

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user
RUN groupadd -g 10001 docuvision && \
    useradd -u 10001 -g docuvision -s /bin/bash -m docuvision

# Install dependencies first for build caching
COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and assets
COPY src/ /app/src/
COPY examples/ /app/examples/
COPY README.md LICENSE /app/

# Install docuvision in editable mode
RUN pip install --no-cache-dir -e .

# Create persistent storage directories with non-root ownership
RUN mkdir -p /home/docuvision/.docuvision /app/outputs && \
    chown -R docuvision:docuvision /home/docuvision /app

USER docuvision

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["docuvision"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
