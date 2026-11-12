#!/usr/bin/env bash
# Shows that the same data survives (1) an application restart and (2) a
# database dump and reload into a fresh database.
#
# Uses two throwaway databases and removes them afterwards. Needs the
# PostgreSQL client tools and a role allowed to create databases.
set -euo pipefail
cd "$(dirname "$0")/.."

export STOREAPP_DEMO_MODE=1
export PGHOST="${STOREAPP_DB_HOST:-127.0.0.1}" PGPORT="${STOREAPP_DB_PORT:-5432}"
export PGUSER="${STOREAPP_DB_USER:-storeapp}" PGPASSWORD="${STOREAPP_DB_PASSWORD:-storeapp}"
SOURCE_DB=storeapp_persist_source
RELOAD_DB=storeapp_persist_reload
PORT=8765
WORK="$(mktemp -d)"
SERVER_PID=""

cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
  dropdb --if-exists "$SOURCE_DB"
  dropdb --if-exists "$RELOAD_DB"
  rm -rf "$WORK"
}
trap cleanup EXIT

start_app() {
  STOREAPP_DB_NAME="$1" python manage.py runserver "127.0.0.1:$PORT" --noreload >"$WORK/server.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then return 0; fi
    sleep 0.25
  done
  echo "The app did not start:"; cat "$WORK/server.log"; exit 1
}
stop_app() { kill "$SERVER_PID"; wait "$SERVER_PID" 2>/dev/null || true; SERVER_PID=""; }
summary() { STOREAPP_DB_NAME="$1" python manage.py stock_summary; }

dropdb --if-exists "$SOURCE_DB"; dropdb --if-exists "$RELOAD_DB"
createdb "$SOURCE_DB"
STOREAPP_DB_NAME="$SOURCE_DB" python manage.py migrate --noinput >/dev/null
STOREAPP_DB_NAME="$SOURCE_DB" python manage.py seed_demo >/dev/null

echo "1. Start the app, read the data, stop it."
start_app "$SOURCE_DB"; summary "$SOURCE_DB" >"$WORK/before.json"; stop_app

echo "2. Start the app again and read the same data."
start_app "$SOURCE_DB"; summary "$SOURCE_DB" >"$WORK/after_restart.json"; stop_app
diff "$WORK/before.json" "$WORK/after_restart.json"

echo "3. Dump the database and reload it into a new, empty database."
pg_dump --format=custom --file="$WORK/storeapp.dump" "$SOURCE_DB"
createdb "$RELOAD_DB"
pg_restore --no-owner --dbname="$RELOAD_DB" "$WORK/storeapp.dump"
start_app "$RELOAD_DB"; summary "$RELOAD_DB" >"$WORK/after_reload.json"; stop_app
diff "$WORK/before.json" "$WORK/after_reload.json"

echo "4. The reloaded database still refuses to rewrite history."
if psql -q -d "$RELOAD_DB" -c "UPDATE inventory_stockmovement SET gross_weight = 1" 2>"$WORK/tamper.log"; then
  echo "FAILED: the stock ledger accepted an UPDATE after reload"; exit 1
fi
grep -q "append-only" "$WORK/tamper.log"

echo "OK: stock, receipts, invoice links and history are identical after a restart and after a dump and reload."
cat "$WORK/before.json"
