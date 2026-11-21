#!/usr/bin/env bash
# Backs up the database and uploaded resumes into ./backups, keeping the last 30 days.
#   bash deploy/backup.sh
# Restore a database backup:
#   gunzip -c backups/db-YYYYMMDD-HHMM.sql.gz | docker compose exec -T db psql -U srk -d srk_placement
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M)
docker compose exec -T db pg_dump -U srk -d srk_placement | gzip > "backups/db-${STAMP}.sql.gz"
docker compose exec -T app tar czf - -C /app/backend uploads > "backups/uploads-${STAMP}.tar.gz"
find backups -name 'db-*.sql.gz' -mtime +30 -delete
find backups -name 'uploads-*.tar.gz' -mtime +30 -delete
echo "$(date) backup ok: db-${STAMP}.sql.gz, uploads-${STAMP}.tar.gz"
