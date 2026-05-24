from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

# POS floor names (case-insensitive) that map to valid restaurant zones.
_VALID_FLOOR_KEYWORDS = ("interior", "patio")


def post_init_hook(cr, registry):
    """Deactivate tables that do not belong to a valid restaurant floor.

    Valid floors are those whose name contains 'interior' or 'patio'.
    This keeps the reservation system in sync with the POS floor plan
    without requiring any manual DB steps.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Find valid floor IDs by name
    all_floors = env["restaurant.floor"].sudo().search([])
    valid_floor_ids = set()
    for floor in all_floors:
        fname = (floor.name or "").strip().lower()
        if any(kw in fname for kw in _VALID_FLOOR_KEYWORDS):
            valid_floor_ids.add(floor.id)

    _logger.info("Valid floor IDs for reservations: %s", valid_floor_ids)

    # Deactivate tables on non-valid floors
    tables = env["restaurant.table"].sudo().with_context(active_test=False).search([])
    to_deactivate = tables.filtered(
        lambda t: not t.floor_id or t.floor_id.id not in valid_floor_ids
    )
    to_activate = tables.filtered(
        lambda t: t.floor_id and t.floor_id.id in valid_floor_ids
    )

    if to_deactivate:
        to_deactivate.write({"active": False})
    if to_activate:
        to_activate.write({"active": True})

    _logger.info(
        "Table sync complete: %s active, %s deactivated",
        len(to_activate),
        len(to_deactivate),
    )