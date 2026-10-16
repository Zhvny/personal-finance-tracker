# ============================================================
# packages/web — Dockerfile (Vite + vite preview)
# ============================================================

FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --no-audit --no-fund

# Copy source and build
COPY . .
ENV NODE_ENV=development
RUN npm run build

# Production runner
FROM node:22-alpine AS production

WORKDIR /app

ENV NODE_ENV=production

# Copy build output, server, and node_modules from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server.js ./server.js
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# Runtime config: Vite injects this into window.__API_BASE__ at build time
# The Node.js proxy in server.js forwards /api/* to the gateway
ENV VITE_API_BASE=/api
# API proxy target (gateway service DNS inside Docker network)
ENV API_TARGET=http://gateway:8444

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://localhost:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
