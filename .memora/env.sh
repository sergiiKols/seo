# memora — SEO-участок. Локально, без облака, без LLM-вызовов при записи.
export MEMORA_DB_PATH=/root/seo/.memora/memories.db
export MEMORA_LLM_ENABLED=0          # дедуп и insights гоняем вручную, не на каждую запись
export MEMORA_ALLOW_ANY_TAG=1
export MEMORA_STALE_DAYS=90
# Облако намеренно выключено: сервер самохостится, часть проектов конфиденциальна.
unset MEMORA_STORAGE_URI MEMORA_CLOUD_GRAPH_ENABLED CLOUDFLARE_API_TOKEN CF_API_TOKEN
unset OPENAI_API_KEY OPENAI_BASE_URL
export MEMORA_EMBEDDING_MODEL=tfidf
