#!/bin/bash
# Clear operational history on CORE FIGHTER VPS DB.
# Keeps: users, stores, wordpress_sites, personas, content_rules
set -euo pipefail
cd /home/admin/Corefighter

echo "=== Before ==="
docker compose exec -T db psql -U corefighter -d corefighter -c \
  "SELECT relname AS tbl, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

echo "=== Truncating history tables ==="
docker compose exec -T db psql -U corefighter -d corefighter <<'SQL'
BEGIN;
TRUNCATE TABLE
  corpus_embeddings,
  published_corpus,
  similarity_results,
  activity_logs,
  jobs,
  article_versions,
  articles,
  purchase_products,
  purchase_images,
  purchases
RESTART IDENTITY CASCADE;
COMMIT;
SQL

echo "=== Flush Redis job queue ==="
docker compose exec -T redis redis-cli FLUSHDB || true

echo "=== After ==="
docker compose exec -T db psql -U corefighter -d corefighter -c \
  "SELECT relname AS tbl, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

echo "=== Kept seed config ==="
docker compose exec -T db psql -U corefighter -d corefighter -c \
  "SELECT 'users' AS t, count(*) FROM users
   UNION ALL SELECT 'stores', count(*) FROM stores
   UNION ALL SELECT 'wordpress_sites', count(*) FROM wordpress_sites
   UNION ALL SELECT 'personas', count(*) FROM personas
   UNION ALL SELECT 'content_rules', count(*) FROM content_rules;"

echo "Done."
