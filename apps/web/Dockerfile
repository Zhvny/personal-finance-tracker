# ============================================================
# apps/web — Dockerfile (Next.js)
# ============================================================

FROM node:22-alpine AS development

WORKDIR /app

# Install pnpm non-interactively
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable && corepack prepare pnpm@11.0.0 --activate

# Copy workspace manifests & source code
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/web ./apps/web

# Install dependencies for workspace
RUN pnpm install --frozen-lockfile

WORKDIR /app/apps/web

EXPOSE 3000

CMD ["pnpm", "dev"]

# ── Builder: Build for production ─────────────────────────
FROM development AS builder

WORKDIR /app/apps/web

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

ARG NEXT_PUBLIC_API_URL=http://localhost:8444
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL

RUN pnpm build

# ── Production runner ─────────────────────────────────────
FROM node:22-alpine AS production

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Standalone output preserves the monorepo path (server lives at
# standalone/apps/web/server.js). Relocate OUTSIDE /app: the dev
# bind-mounts (./apps/web, ./packages) shadow everything under /app
# at runtime, which hid server.js and crashed the container.
COPY --from=builder /app/apps/web/.next/standalone /srv/web
COPY --from=builder /app/apps/web/public /srv/web/apps/web/public
COPY --from=builder /app/apps/web/.next/static /srv/web/apps/web/.next/static

WORKDIR /srv/web/apps/web

USER nextjs

EXPOSE 3000

ENV PORT=3000

CMD ["node", "server.js"]
