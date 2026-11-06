# Multi-arch image (linux/amd64 for the ODROID-H3+, linux/arm64 for the ODROID-N2L).
#   docker buildx build --platform linux/amd64,linux/arm64 -f deploy/docker/Dockerfile .
# Dependencies come from uv.lock; on Linux torch resolves to CPU-only wheels.

ARG PYTHON_VERSION=3.11
ARG UV_VERSION=0.13.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app

# 1) Third-party deps only (cached layer, invalidated only by lockfile changes).
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) The project itself.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
RUN useradd --create-home --uid 1000 edge
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY configs ./configs
USER edge

# Role is chosen at run time, e.g. `python -m edge_fl.fl.client`.
CMD ["python", "-m", "edge_fl.fl.server"]
