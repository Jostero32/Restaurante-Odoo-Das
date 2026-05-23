from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tables = env["restaurant.table"].sudo().search([], order="id asc")

    for index, table in enumerate(tables, start=1):
        zone = "main" if index <= 11 else "patio" if index <= 18 else "main"
        table.write(
            {
                "name": str(index),
                "zone": zone,
                "active": index <= 18,
            }
        )