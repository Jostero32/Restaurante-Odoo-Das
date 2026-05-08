#!/usr/bin/env bash
set -euo pipefail

DB_NAME=${DB_NAME:-odoo}

if [ ! -f "backups/db_demo.dump" ]; then
  echo "Missing backups/db_demo.dump"
  exit 1
fi

if [ ! -d "backups/filestore/$DB_NAME" ]; then
  echo "Missing backups/filestore/$DB_NAME"
  exit 1
fi

# Recreate database

docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker compose exec -T db psql -U odoo -d postgres -c "CREATE DATABASE $DB_NAME;"

docker compose exec -T db pg_restore -U odoo -d "$DB_NAME" /backups/db_demo.dump

# Restore filestore

docker compose exec -T odoo bash -lc "rm -rf /var/lib/odoo/filestore/$DB_NAME; mkdir -p /var/lib/odoo/filestore/$DB_NAME; cp -a /backups/filestore/$DB_NAME/. /var/lib/odoo/filestore/$DB_NAME/; chown -R odoo:odoo /var/lib/odoo/filestore/$DB_NAME"

echo "Restore completed. Restarting Odoo..."
docker compose restart odoo