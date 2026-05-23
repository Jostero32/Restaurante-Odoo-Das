from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

# Map POS floor names to reservation zones
_FLOOR_ZONE_MAP = {
    "interior": "main",
    "patio": "patio",
}

# POS floor IDs that are valid for the restaurant
_VALID_FLOOR_IDS = {7, 10}  # 7=Interior, 10=Patio


def _sync_table_zones(env):
    """Synchronize table zones based on the POS floor assignment.

    Maps each table's zone from its floor_id name:
      - Floors with 'interior' in the name → zone 'main'
      - Floors with 'patio' in the name   → zone 'patio'
      - Tables on non-valid floors         → deactivated
    """
    tables = env["restaurant.table"].sudo().search([], order="id asc")
    counter = {"main": 0, "patio": 0}

    for table in tables:
        floor_id = table.floor_id.id if hasattr(table, "floor_id") and table.floor_id else None
        floor_name = (table.floor_id.name or "").strip().lower() if hasattr(table, "floor_id") and table.floor_id else ""

        # Determine zone from floor name
        zone = None
        for keyword, zone_code in _FLOOR_ZONE_MAP.items():
            if keyword in floor_name:
                zone = zone_code
                break

        # Only activate tables on valid floors with a recognized zone
        if zone and floor_id in _VALID_FLOOR_IDS:
            counter[zone] = counter.get(zone, 0) + 1
            table.write({
                "name": str(counter[zone]),
                "zone": zone,
                "active": True,
            })
        else:
            table.write({"active": False})

    _logger.info(
        "Table zone sync complete: %s interior, %s patio, %s total active",
        counter.get("main", 0),
        counter.get("patio", 0),
        sum(counter.values()),
    )


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _sync_table_zones(env)