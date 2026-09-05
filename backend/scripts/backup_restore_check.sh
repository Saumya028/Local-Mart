#!/usr/bin/env bash
set -euo pipefail

# Phase 7 reliability check: "Database backups confirmed and a restore
# actually tested once (a backup you've never restored isn't a backup)."
#
# Supabase takes automatic backups for you (daily on paid plans, with
# point-in-time recovery on higher tiers) — this script does NOT
# replace that, and it can't be run from inside this sandbox (no
# network access to your actual Supabase project from here). What it
# DOES do is give you a repeatable way to prove to yourself, right now,
# that a backup of your schema+data can actually be restored — not just
# that a backup file exists somewhere.
#
# Usage:
#   DATABASE_URL="postgresql://postgres:PASSWORD@HOST:5432/postgres" \
#     ./scripts/backup_restore_check.sh
#
# Use the DIRECT connection string here (Supabase: Settings -> Database
# -> Connection string -> "URI", NOT the pooler/pgbouncer one) — pg_dump
# needs a plain synchronous connection, and this script also does not
# want the `+asyncpg` driver prefix the app's own DATABASE_URL uses.
#
# What it does:
#   1. pg_dump your real database to a local .sql file (a real backup).
#   2. Spin up a throwaway local Postgres in Docker.
#   3. Restore the dump into that throwaway database.
#   4. Run a couple of sanity queries against the restored copy.
#   5. Tear the throwaway database down.
#
# Nothing here touches your real database except reading from it.

: "${DATABASE_URL:?Set DATABASE_URL to your Supabase DIRECT connection string first}"

command -v pg_dump >/dev/null || { echo "pg_dump not found — install the postgresql-client package"; exit 1; }
command -v docker >/dev/null || { echo "docker not found — needed to spin up a throwaway restore target"; exit 1; }

DUMP_FILE="localmart_backup_$(date +%Y%m%d_%H%M%S).sql"
CONTAINER_NAME="localmart-restore-check"

echo "==> Step 1/4: dumping the real database to ${DUMP_FILE}"
pg_dump "$DATABASE_URL" --no-owner --no-privileges -f "$DUMP_FILE"
echo "    $(du -h "$DUMP_FILE" | cut -f1) written."

echo "==> Step 2/4: starting a throwaway local Postgres"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER_NAME" \
  -e POSTGRES_PASSWORD=restorecheck \
  -p 55432:5432 \
  postgres:16 >/dev/null
echo "    waiting for it to accept connections..."
for _ in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done

RESTORE_URL="postgresql://postgres:restorecheck@localhost:55432/postgres"

echo "==> Step 3/4: restoring the dump into the throwaway database"
psql "$RESTORE_URL" -q -f "$DUMP_FILE"

echo "==> Step 4/4: sanity-checking the restored data"
psql "$RESTORE_URL" -c "
  SELECT
    (SELECT count(*) FROM profiles) AS profiles,
    (SELECT count(*) FROM shops)    AS shops,
    (SELECT count(*) FROM products) AS products,
    (SELECT count(*) FROM orders)   AS orders;
"

echo "==> Cleaning up"
docker rm -f "$CONTAINER_NAME" >/dev/null

echo ""
echo "Restore check complete. If the counts above look sane (non-zero,"
echo "roughly matching what you expect), your backups are provably"
echo "restorable — not just something Supabase says exists."
echo ""
echo "Keep ${DUMP_FILE} if you want a local copy, or delete it — it's"
echo "not needed by anything else. Run this periodically (e.g. monthly,"
echo "or before any risky migration), not just once."
