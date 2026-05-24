from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RestaurantTable(models.Model):
    _inherit = "restaurant.table"

    # ------------------------------------------------------------------
    # Computed zone derived from the POS floor name.
    # Non-stored so it doesn't require any DB migration.
    # "Interior" floor → "main"  |  "Patio" floor → "patio"
    # ------------------------------------------------------------------
    zone = fields.Selection(
        [
            ("main", "Interior"),
            ("patio", "Patio"),
        ],
        string="Zona",
        compute="_compute_zone",
        search="_search_zone",
    )

    @api.depends("floor_id", "floor_id.name")
    def _compute_zone(self):
        for table in self:
            floor_name = (
                (table.floor_id.name or "").strip().lower()
                if table.floor_id
                else ""
            )
            if "interior" in floor_name:
                table.zone = "main"
            elif "patio" in floor_name:
                table.zone = "patio"
            else:
                table.zone = False

    def _search_zone(self, operator, value):
        """Allow domain filters like [('zone', '=', 'main')]."""
        floors = self.env["restaurant.floor"].sudo().search([])
        floor_ids = []
        for floor in floors:
            fname = (floor.name or "").strip().lower()
            if value == "main" and "interior" in fname:
                floor_ids.append(floor.id)
            elif value == "patio" and "patio" in fname:
                floor_ids.append(floor.id)
        if operator in ("=", "in"):
            return [("floor_id", "in", floor_ids)]
        elif operator in ("!=", "not in"):
            return [("floor_id", "not in", floor_ids)]
        return [("floor_id", "in", floor_ids)]

    @api.constrains("seats")
    def _check_seats(self):
        for table in self:
            if table.seats <= 0:
                raise ValidationError(
                    _("La capacidad de la mesa debe ser mayor a cero.")
                )
