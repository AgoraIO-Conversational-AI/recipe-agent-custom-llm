# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS runtime

# Run as a non-root user (created before any COPY so --chown can reference it).
RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Python dependencies for both backend services (installed as root into the
# system site-packages, world-readable for the app user at runtime).
COPY server/requirements.txt /tmp/server-req.txt
COPY llm/requirements.txt /tmp/llm-req.txt
RUN pip install --no-cache-dir -r /tmp/server-req.txt -r /tmp/llm-req.txt

# Python source, owned by the runtime user.
COPY --chown=app:app server/src /app/server/src
COPY --chown=app:app llm/src /app/llm/src

# Launcher (server + llm).
COPY --chown=app:app docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

# Drop privileges for the running processes.
USER app

EXPOSE 8000 8001
CMD ["/app/docker/entrypoint.sh"]
