#!/usr/bin/with-contenv bashio
set -e

LOG_LEVEL="$(bashio::config 'log_level')"
export WEBAPP_LOG_LEVEL="${LOG_LEVEL:-info}"
EXTERNAL_URL="$(bashio::config 'external_url')"
export WEBAPP_EXTERNAL_URL="${EXTERNAL_URL:-}"

export LEARNING_AI_URL="$(bashio::config 'learning_ai_url')"
export LEARNING_AI_KEY="$(bashio::config 'learning_ai_key')"
export LEARNING_AI_MODEL="$(bashio::config 'learning_ai_model')"

bashio::log.info "Starting Schul-Cockpit on ${WEBAPP_HOST}:${WEBAPP_PORT}"
bashio::log.info "history.db: ${WEBAPP_HISTORY_DB}"
bashio::log.info "data dir:   ${WEBAPP_DATA_DIR}"

cd /app
exec python -m uvicorn backend.main:app \
    --host "${WEBAPP_HOST}" \
    --port "${WEBAPP_PORT}" \
    --log-level "${WEBAPP_LOG_LEVEL}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
