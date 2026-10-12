# Voice Stack: one image for every role (ROLE=all | app | telephony).

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY examples/ /app/examples/
COPY --from=web /web/dist /app/frontend/dist

# Optional: bake the local embedding model into the image so the first upload does not download it.
ARG PRELOAD_EMBEDDINGS=false
ENV DATA_DIR=/app/data PATH="/app/backend/.venv/bin:$PATH" PORT=8000
RUN mkdir -p /app/data && if [ "$PRELOAD_EMBEDDINGS" = "true" ]; then \
      python -c "from voicestack.knowledge.embeddings import get_embeddings; get_embeddings().embed_query('warm up')"; fi

# Source files keep the build host's modes; make them readable for the non-root runtime user.
RUN chmod -R a+rX /app && useradd --create-home --uid 10001 voicestack && chown -R voicestack /app/data
USER voicestack
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/healthz', timeout=4)"
CMD ["sh", "-c", "exec voicestack serve --port ${PORT}"]
