FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# Dev-mode only: local Docker Compose runs the Next.js dev server with hot
# reload (source is bind-mounted over this COPY at runtime — see
# docker-compose.yml). Production is a static export deployed to Cloudflare
# Pages directly from `next build`, never through this Dockerfile or
# `next start` — those are incompatible with `output: export` in
# next.config.ts and must not be reintroduced here.
# --webpack (not the Turbopack default): Turbopack's native watcher never
# receives events for edits made from the host through Docker Desktop's
# bind-mount filesystem on macOS, so hot reload silently never fires.
# Webpack's chokidar-based watcher honors CHOKIDAR_USEPOLLING and does.
CMD ["npx", "next", "dev", "--webpack", "-H", "0.0.0.0", "-p", "3000"]
