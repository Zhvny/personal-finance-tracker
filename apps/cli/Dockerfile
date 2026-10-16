# ============================================================
# apps/cli — Dockerfile (Python CLI)
# ============================================================
# Run interactively via:
#   docker compose run --rm cli
# ============================================================

FROM python:3.12-slim

WORKDIR /app

# System deps: Tesseract OCR + PostgreSQL client libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-ind \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY apps/cli/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy shared packages and CLI source
COPY packages/ ./packages/
COPY apps/cli/ ./apps/cli/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command: launch the interactive CLI
CMD ["python", "apps/cli/main.py"]
