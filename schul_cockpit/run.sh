#!/usr/bin/with-contenv bashio
set -e

LOG_LEVEL="$(bashio::config 'log_level')"
export WEBAPP_LOG_LEVEL="${LOG_LEVEL:-info}"
EXTERNAL_URL="$(bashio::config 'external_url')"
export WEBAPP_EXTERNAL_URL="${EXTERNAL_URL:-}"

# KI-Plattformen und Modellstufen kommen als verschachtelte Optionen. Statt
# jedes Blatt einzeln über bashio zu holen, werden die beiden Blöcke direkt aus
# der Optionsdatei als kompaktes JSON gereicht; das Backend liest sie.
AI_OPTIONS=/data/options.json
if [ -f "$AI_OPTIONS" ]; then
  export LEARNING_AI_PLATFORMS="$(jq -c '.ki_plattformen // {}' "$AI_OPTIONS")"
  export LEARNING_AI_MODELS="$(jq -c '.ki_modelle // {}' "$AI_OPTIONS")"
else
  bashio::log.warning "Optionsdatei ${AI_OPTIONS} nicht gefunden; KI bleibt aus."
  export LEARNING_AI_PLATFORMS="{}"
  export LEARNING_AI_MODELS="{}"
fi

export LEARNING_READ_TOKEN="$(bashio::config 'learning_read_token')"
export LEARNING_READ_ACCOUNTS="$(bashio::config 'learning_read_accounts')"

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
