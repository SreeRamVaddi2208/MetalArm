# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# LevelForge frontend (Reflex).
#
# Reflex owns the Node/React/Next.js build entirely. We never hand-write or
# copy in a package.json / package-lock.json - Reflex generates its lockfile
# INSIDE this linux container, against this container's platform. That is what
# kills the previous project's failure mode: a darwin-generated lockfile fed to
# a linux container via `npm ci`.
#
# IMPORTANT: api_url is baked into the compiled JS bundle at BUILD time, not
# read at runtime. It is therefore a build ARG. If you change which host the
# browser should reach Reflex's state server on, you must REBUILD, not just
# restart.
# ---------------------------------------------------------------------------

FROM python:3.14-slim

# curl + unzip: Reflex uses them to fetch its managed bun/node toolchain.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system levelforge \
    && useradd --system --gid levelforge --home-dir /app levelforge

WORKDIR /app

# Dependency layer first, so editing UI code doesn't reinstall Reflex.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=levelforge:levelforge . .
RUN chown -R levelforge:levelforge /app

USER levelforge

# Reflex writes its toolchain + build output under HOME and /app/.web.
ENV HOME=/app

# Reflex PROD mode requires frontend_port == backend_port (reflex.py:358):
# a single granian process serves both the SSR frontend and the state server.
# Hence 3000 for both here, unlike local dev which splits 3000/8001.
ARG REFLEX_API_URL=http://localhost:3000
ARG REFLEX_FRONTEND_PORT=3000
ARG REFLEX_BACKEND_PORT=3000
ENV REFLEX_API_URL=${REFLEX_API_URL} \
    REFLEX_FRONTEND_PORT=${REFLEX_FRONTEND_PORT} \
    REFLEX_BACKEND_PORT=${REFLEX_BACKEND_PORT}

# Compile the frontend at build time so container start is fast and any
# compile error fails the BUILD rather than surfacing as a broken runtime.
RUN reflex export --frontend-only --no-zip --env prod

EXPOSE 3000

CMD ["reflex", "run", "--env", "prod"]
