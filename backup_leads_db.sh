#!/bin/bash
# Daily backup of leads.db for Turnover Titans.
# Uses sqlite3's online .backup command so it's safe to run while
# form_catcher.py has the database open for writes.
set -euo pipefail

REPO_DIR="/home/made4derrick/turnover-titans"
DB_PATH="$REPO_DIR/data/leads.db"
BACKUP_DIR="$REPO_DIR/data/backups"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') leads.db not found at $DB_PATH, skipping backup"
    exit 0
fi

STAMP="$(date '+%Y%m%d_%H%M%S')"
DEST="$BACKUP_DIR/leads_${STAMP}.db"

sqlite3 "$DB_PATH" ".backup '$DEST'"
echo "$(date '+%Y-%m-%d %H:%M:%S') backed up $DB_PATH -> $DEST"

find "$BACKUP_DIR" -name 'leads_*.db' -mtime "+${RETENTION_DAYS}" -print -delete
