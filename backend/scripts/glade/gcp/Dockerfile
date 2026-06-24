# Cloud Run image for the Void Ranger FastAPI backend (Phase 2G.4, optional).
#
# Used by `30_serve.sh run`. `gcloud run deploy` has NO --dockerfile flag: Cloud
# Build auto-detects a Dockerfile at the root of the --source dir. So the script
# copies this file to the backend/ root for the build (and removes it after).
# The BUILD CONTEXT is therefore backend/; paths below are relative to backend/.
#
# Only needed if you serve the grid/API from the backend instead of static GCS.
# The image installs deps with uv against the committed uv.lock (no corp mirror;
# pyproject pins public PyPI), then runs uvicorn on $PORT (Cloud Run sets PORT).

FROM python:3.11-slim

# uv: fast, lockfile-faithful installs. Copy the static binary from the official
# image (pinned tag for reproducibility).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Install dependencies first (cached layer) using only the lock + manifest.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App source + the data the API reads at runtime. data/samples/deepfield/grid is
# the committed N=48 SAMPLE grid (the in-image default the backend loads when
# DEEPFIELD_GRID_DIR is unset). 30_serve.sh `run` mode additionally stages the
# full-catalog grid into data/deepfield_prod/grid (fetched from GCS) and sets
# DEEPFIELD_GRID_DIR to it, so production serves physics from the full grid; the
# exaggeration is auto-derived per grid, so no rebuild/tuning is needed.
COPY app ./app
COPY data ./data

# Finish installing the project itself into the env.
RUN uv sync --frozen --no-dev

# Cloud Run injects PORT (default 8080); bind uvicorn to it. Use sh -c so the
# env var expands at runtime.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
