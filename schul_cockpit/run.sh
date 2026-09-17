#!/usr/bin/with-contenv bashio
set -e

LOG_LEVEL="$(bashio::config 'log_level')"
export WEBAPP_LOG_LEVEL="${LOG_LEVEL:-info}"
EXTERNAL_URL="$(bashio::config 'external_url')"
export WEBAPP_EXTERNAL_URL="${EXTERNAL_URL:-}"

export LEARNING_AI_URL="$(bashio::config 'learning_ai_url')"
export LEARNING_AI_KEY="$(bashio::config 'learning_ai_key')"
export LEARNING_AI_MODEL="$(bashio::config 'learning_ai_model')"
# Zweiter Foundry-Zugang: Deployments aus der Liste laufen ausschließlich dort.
# bashio gibt eine Listenoption als JSON aus; das Backend nimmt die Rohform
# entgegen und trennt selbst an Komma und Zeile.
export LEARNING_AI_URL_2="$(bashio::config 'learning_ai_url_2')"
export LEARNING_AI_KEY_2="$(bashio::config 'learning_ai_key_2')"
export LEARNING_AI_MODELS_2="$(bashio::config 'learning_ai_models_2')"
export LEARNING_AI_TRANSCRIBE_MODEL="$(bashio::config 'learning_ai_transcribe_model')"
export LEARNING_AI_TRANSCRIBE_URL="$(bashio::config 'learning_ai_transcribe_url')"

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
