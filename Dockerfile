# syntax=docker/dockerfile:1

# ---------- Stage 1: build the Next.js standalone web bundle with Bun ----------
FROM oven/bun:1 AS web-build
WORKDIR /src
# Install workspace deps first (better layer caching). The repo is a Bun
# workspace whose root package.json declares workspaces: ["web"].
COPY package.json bun.lock ./
COPY web/package.json web/package.json
RUN bun install --frozen-lockfile
# Build the web app -> web/.next/standalone (server.js nested under web/).
# DOCKER_BUILD=1 makes next.config skip the TypeScript type-check so the build
# fits in modest memory (type checks run in the normal build + test CI instead).
ENV DOCKER_BUILD=1
COPY web/ web/
RUN bun run build

# ---------- Stage 2: runtime with node (for web) + python (for server/llm) ----------
FROM node:22-bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app

# Python dependencies for both backend services.
COPY server/requirements.txt /tmp/server-req.txt
COPY llm/requirements.txt /tmp/llm-req.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/server-req.txt -r /tmp/llm-req.txt

# Python source.
COPY server/src /app/server/src
COPY llm/src /app/llm/src

# Web standalone bundle: the standalone root holds node_modules/ + web/server.js.
# Copying it to /app yields /app/node_modules and /app/web/server.js.
COPY --from=web-build /src/web/.next/standalone/ /app/
# static + public are NOT included in standalone — place them under the nested web dir.
COPY --from=web-build /src/web/.next/static /app/web/.next/static
COPY --from=web-build /src/web/public /app/web/public

# Launcher.
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

# web -> server is internal in-container; overridable at runtime.
ENV AGENT_BACKEND_URL=http://localhost:8000

EXPOSE 3000 8000 8001
CMD ["/app/docker/entrypoint.sh"]
