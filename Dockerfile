# syntax=docker/dockerfile:1
# CandidatAI en Docker (fase 26.3). Opcional: la forma recomendada es la instalación
# nativa (install.ps1, install.sh). Tu agente de IA vive fuera del contenedor y usa la app por MCP
# (`docker exec -i candidatai cai-mcp`) o por `cai … --json`. Ver «Con Docker» en la guía.
#
#   docker compose up -d --build
#
# La imagen no lleva datos personales: tus datos van en el volumen `/data` (ver .dockerignore).

# --- UI compilada ----------------------------------------------------------------------------
FROM node:24-slim AS ui
WORKDIR /src/frontend
RUN npm install --global pnpm@12.6.0
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
# Algunos tests del frontend leen `../extension`; `tsc -b` los compila.
COPY extension/ /src/extension/
RUN pnpm build

# --- App -------------------------------------------------------------------------------------
# uv fijado: la misma imagen base en cada construcción.
FROM ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/backend/.venv/bin:$PATH \
    CAI_IN_DOCKER=1 \
    CAI_DATA_DIR=/data

WORKDIR /app/backend

# Primero las dependencias: cambian menos que el código y así se reaprovecha la capa. La caché de
# uv va en un montaje de la construcción, no en la imagen.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Chromium sin ventana, con sus librerías: imprime los PDF del motor html. Sin LibreOffice: el
# motor html basta. La candidatura asistida (navegador visible) no funciona dentro.
RUN playwright install --with-deps --only-shell chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
COPY --from=ui /src/frontend/dist /app/frontend/dist
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Usuario sin privilegios, dueño solo de sus datos.
RUN useradd --create-home --uid 1000 cai \
    && mkdir /data /data-demo \
    && chown cai:cai /data /data-demo
USER cai
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/status', timeout=4)"]

CMD ["cai", "start", "--no-browser"]
