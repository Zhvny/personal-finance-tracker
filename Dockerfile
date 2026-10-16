# Stage 1: Build Python dependencies
FROM python:3.12-alpine AS python-builder
WORKDIR /app
# openmp-dev: scikit-learn needs OpenMP headers at build time
# g++ cmake: xgboost compiles from source on alpine (no wheels available)
# linux-headers: build tools for psutil
RUN apk add --no-cache gcc g++ musl-dev postgresql-dev openmp-dev cmake linux-headers
COPY requirements.prod.txt .
RUN pip install --user --no-cache-dir -r requirements.prod.txt

# Stage 2: Final Runtime (backend only; frontend apps/web punya Dockerfile sendiri)
FROM python:3.12-alpine
WORKDIR /app

# Install minimal runtime libraries.
# libgomp: scikit-learn runtime needs OpenMP shared library
# libstdc++: xgboost runtime needs C++ standard library
# openssl: Prisma query-engine binary needs libssl at runtime
RUN apk add --no-cache libpq tesseract-ocr libgomp libstdc++ openssl

COPY --from=python-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY apps/ ./apps/
COPY packages/ ./packages/
COPY services/ ./services/

# Generate Prisma client (services import it at startup; generated code is
# intentionally untracked, so bake it into the image — same as CI's api job).
RUN prisma generate --schema=packages/database/schema.prisma

ENV PYTHONPATH=/app:/app/packages
ENV FINANCE_TRACKER_PORT=8444
EXPOSE 8444

# Default = gateway entry (canonical microservice topology); downstreams
# override via compose `command`
CMD ["python", "-m", "services.gateway.main"]
