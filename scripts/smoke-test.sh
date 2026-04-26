#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "smoke-test: $*" >&2
  exit 1
}

test -f .env || cp .env.example .env

set -a
. ./.env
set +a

command -v npm >/dev/null 2>&1 || fail "npm is required on the host for Prisma migrations. Install Node.js/npm, then run npm install."
test -d apps/web/node_modules || fail "workspace dependencies are missing. Run npm install from the repository root before the smoke test."

has_prisma_migration=false
for migration_dir in apps/web/prisma/migrations/*; do
  [ -d "$migration_dir" ] || continue
  has_prisma_migration=true
  break
done
[ "$has_prisma_migration" = true ] || fail "Prisma migrations are missing. Create and commit migrations before running the smoke test; prisma:migrate would otherwise prompt for a migration name."

host_database_url="${HOST_DATABASE_URL:-}"
if [ -z "$host_database_url" ]; then
  [ -n "${DATABASE_URL:-}" ] || fail "DATABASE_URL is empty. Host Prisma needs a host-reachable DB URL; set HOST_DATABASE_URL in .env."
  host_database_url="${DATABASE_URL//@postgres:/@localhost:}"
  host_database_url="${host_database_url//@postgres\//@localhost/}"
fi

if [ -z "$host_database_url" ] || [[ "$host_database_url" =~ @postgres([:/?#]|$) ]]; then
  fail "host Prisma needs a host-reachable DB URL. Set HOST_DATABASE_URL in .env, for example postgresql://autofacodex:autofacodex@localhost:5432/autofacodex."
fi

wait_for_postgres() {
  local max_attempts=30
  local attempt

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-autofacodex}" -d "${POSTGRES_DB:-autofacodex}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  fail "Postgres did not become ready after ${max_attempts} attempts. Check docker compose logs postgres."
}

docker compose up -d postgres redis
wait_for_postgres
DATABASE_URL="$host_database_url" npm --workspace apps/web run prisma:migrate
docker compose up -d web worker
docker compose ps
