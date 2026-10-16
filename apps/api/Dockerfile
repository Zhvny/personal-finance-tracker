# ============================================================
# apps/api — Dockerfile (Alpha Microservice)
# ============================================================
# A-003: LEGACY — kept for reference; the canonical image is the root
# `Dockerfile` (services gateway). The microservice split retired this
# monolithic image. Do not build or push; if you need to debug the old
# monolith, use `python -m apps.api.main` instead.
# Multi-stage build:
#   stage 1 (builder):  install Python deps + generate Prisma client
#                       (nodejs is required HERE for the Prisma CLI only)
#   stage 2 (base):     slim runtime — NO nodejs, NO build tools
#
# Targets:
#   production (default) — plain uvicorn, no hot reload (lightweight)
#   development          — uvicorn --reload + nodejs for on-the-fly
#                          `prisma generate` on schema changes
#
# Note: the Prisma client is generated at BUILD time, so the runtime
# image does not need nodejs (saves ~150-200MB). The engine binary is
# downloaded once during the build and cached in the image.

# ── Stage 1: Builder (deps + prisma generate) ────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# nodejs is only needed to run the Prisma CLI during `generate`
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (precompiled wheels, no gcc needed)
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy schema + shared packages needed by the generator
COPY packages/ ./packages/

ENV PYTHONPATH=/app
ENV PRISMA_PY_DEBUG_GENERATOR=1
ENV PRISMA_BINARY_CACHE_DIR=/root/.cache/prisma-binaries
# A-002: placeholder for prisma generate at build time. The build step
# only parses the schema, never opens a connection. The runtime
# DATABASE_URL is injected by compose / deployment; the
# `apps/api/config.py` fail-fast guard (empty + "placeholder" rejection)
# catches any real deploy that forgets to set it.
ENV DATABASE_URL="postgresql://placeholder:placeholder@localhost:5432/placeholder?schema=public"
# `prisma generate` only parses the schema; the URL is overridden at
# runtime by packages/database/index.py (per-profile search_path)
ENV DATABASE_URL="postgresql://postgres:postgres@localhost:5432/finance_tracker?schema=public" # pragma: allowlist secret (build-time local default, overridden at runtime)

# Generate the client INTO site-packages (verified: prisma-client-py v0.15.0
# writes to the installed `prisma` package + downloads the query engine here)
RUN python -m prisma generate --schema=/app/packages/database/schema.prisma

# ── Stage 2: Slim runtime ─────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

# libatomic1/openssl — required by the Prisma query engine binary
# tesseract-ocr + tesseract-ocr-ind — receipt OCR (Phase 4, lang="ind+eng")
RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    openssl \
    ca-certificates \
    tesseract-ocr \
    tesseract-ocr-ind \
    && rm -rf /var/lib/apt/lists/*

# Copy generated client + engine binary from builder (same base image)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /root/.cache/prisma-binaries /root/.cache/prisma-binaries

# Copy shared packages and CLI modules needed for domain logic
COPY packages/ ./packages/
COPY apps/cli/ ./apps/cli/
COPY apps/api/ ./apps/api/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PRISMA_PY_DEBUG_GENERATOR=1
ENV PRISMA_BINARY_CACHE_DIR=/root/.cache/prisma-binaries

WORKDIR /app/apps/api

EXPOSE 8444

# ── Production target (default): lightweight, no nodejs ───────
FROM base AS production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8444"]

# ── Development target: hot reload + nodejs for prisma generate ─
FROM base AS development
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    && rm -rf /var/lib/apt/lists/*
CMD ["sh", "-c", "python -m prisma generate --schema=/app/packages/database/schema.prisma && uvicorn main:app --host 0.0.0.0 --port 8444 --reload"]