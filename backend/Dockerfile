# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# MetalArm backend.
#
# Multi-stage so build tooling never reaches the runtime image. Requirements
# are copied and installed BEFORE app source, so editing application code
# reuses the cached dependency layer instead of reinstalling everything.
#
# No apt build deps are needed: fastapi/psycopg2-binary/bcrypt/pydantic-core
# all publish prebuilt cp314 manylinux aarch64 + x86_64 wheels, so this builds
# natively on Apple Silicon and on linux/amd64 CI without a compiler.
# ---------------------------------------------------------------------------

FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build into a venv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# --only-binary=:all: makes a missing wheel fail loudly here rather than
# silently falling back to a source build that breaks on another platform.
RUN pip install --only-binary=:all: -r requirements.txt


FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as an unprivileged user.
RUN groupadd --system metalarm \
    && useradd --system --gid metalarm --create-home metalarm

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=metalarm:metalarm . .

USER metalarm

EXPOSE 8000

# Compose also defines a healthcheck; this keeps the image self-describing
# when run standalone.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------------------------------------------------------------------------
# Test stage. Never part of the default build: `docker compose build backend`
# stops at `runtime`, so pytest and httpx stay out of the shipped image.
#
# Run the suite with:  docker compose run --rm tests
# ---------------------------------------------------------------------------
FROM runtime AS dev

USER root
COPY requirements-dev.txt .
RUN pip install --only-binary=:all: -r requirements-dev.txt
USER metalarm

CMD ["pytest", "-q"]
