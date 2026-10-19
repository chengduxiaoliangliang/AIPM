# ── AIPM frontend ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

# Override if you are not building from mainland China.
ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app
ENV CI=1

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

# Install dependencies first for better layer caching
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --registry=${NPM_REGISTRY} --fetch-timeout=120000

COPY . .
RUN pnpm build:only

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
