ARG BUILD_FROM

# ---------- frontend build stage ----------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- runtime stage ----------
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apk add --no-cache sqlite-libs

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend_dist

ENV PYTHONPATH=/app
ENV WEBAPP_DATA_DIR=/data \
    WEBAPP_HISTORY_DB=/config/untis_archive/history.db \
    WEBAPP_FRONTEND_DIR=/app/frontend_dist \
    WEBAPP_HOST=0.0.0.0 \
    WEBAPP_PORT=8099

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
