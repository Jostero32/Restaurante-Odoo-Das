#!/usr/bin/env bash
set -euo pipefail

DB_NAME=${DB_NAME:-odoo}

# Write backups into ./backups via the /backups bind mount
mkdir -p backups

docker compose exec -T db pg_dump -U odoo -d "$DB_NAME" -F c -f /backups/db_demo.dump

docker compose exec -T odoo bash -lc "rm -rf /backups/filestore/$DB_NAME; mkdir -p /backups/filestore/$DB_NAME; cp -a /var/lib/odoo/filestore/$DB_NAME/. /backups/filestore/$DB_NAME/"

echo "Backup completed in ./backups"