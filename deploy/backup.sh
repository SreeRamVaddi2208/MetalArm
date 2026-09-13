#!/usr/bin/env sh
# On-demand database backup and restore for the production stack.
# (Nightly backups run on their own in the `backup` service.)
#
#   deploy/backup.sh                          write deploy/backups/metalarm-<time>.dump
#   deploy/backup.sh restore <file.dump>      REPLACE the database with a backup
set -eu

cd "$(dirname "$0")"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"

case "${1:-backup}" in
  backup)
    mkdir -p backups
    file="backups/metalarm-$(date -u +%Y%m%dT%H%M%SZ).dump"
    $COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$file"
    echo "backup written: deploy/$file"
    ;;
  restore)
    file="${2:?usage: deploy/backup.sh restore <file.dump>}"
    [ -f "$file" ] || { echo "no such file: $file" >&2; exit 1; }
    printf 'This REPLACES the production database with %s. Type "restore" to continue: ' "$file"
    read -r answer
    [ "$answer" = "restore" ] || { echo "aborted"; exit 1; }
    # Stop writers so nothing lands mid-restore.
    $COMPOSE stop backend frontend
    $COMPOSE exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$file"
    $COMPOSE up -d backend frontend
    echo "restored from $file"
    ;;
  *)
    echo "usage: deploy/backup.sh [backup | restore <file.dump>]" >&2
    exit 2
    ;;
esac
