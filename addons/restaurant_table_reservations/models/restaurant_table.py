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

    current_arrangement = fields.Char(
        string="Arreglo Actual",
        compute="_compute_current_arrangement",
        help="Arreglo especial asociado a la reserva activa de la mesa (si existe).",
    )

    @api.model
    def _get_active_reservation_for_table(self, table_id, reference_datetime=None):
        reference_datetime = reference_datetime or fields.Datetime.now()
        return self.env["restaurant.table.reservation"].sudo().search(
            [
                ("table_id", "=", table_id),
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<=", reference_datetime),
                ("end_datetime", ">=", reference_datetime),
            ],
            order="start_datetime desc, id desc",
            limit=1,
        )

    @api.model
    def get_pos_reservation_snapshot(self, config_id=None):
        now = fields.Datetime.now()
        reservations = self.env["restaurant.table.reservation"].sudo().search(
            [
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<=", now),
                ("end_datetime", ">=", now),
            ]
        )
        snapshot = {}
        for reservation in reservations:
            # find corresponding arrangement product by default_code
            code_map = {
                "birthday": "ARR-BIRTHDAY",
                "anniversary": "ARR-ANNIV",
                "romantic": "ARR-ROMANTIC",
                "general": "ARR-GENERAL",
            }
            product = self.env["product.product"].sudo().search(
                [("default_code", "=", code_map.get(reservation.arrangement_type or "", ""))],
                limit=1,
            )
            # If product not found, create a product.template + variant so POS can reference it later
            if not product and reservation.arrangement_type and reservation.arrangement_type != 'none':
                code = code_map.get(reservation.arrangement_type or "", "")
                try:
                    tmpl_vals = {
                        'name': reservation._get_arrangement_label(reservation.arrangement_type),
                        'default_code': code,
                        'type': 'service',
                        'list_price': arrangement_price,
                        'sale_ok': True,
                        'base_unit_count': 1.0,
                    }
                    tmpl = self.env['product.template'].sudo().create(tmpl_vals)
                    # product.product variant will be created automatically; get it
                    product = tmpl.product_variant_id
                except Exception:
                    product = False
            arrangement_price = reservation._get_arrangement_cost()
            snapshot[reservation.table_id.id] = {
                "reservation_id": reservation.id,
                "table_id": reservation.table_id.id,
                "state": reservation.state,
                "arrangement_type": reservation.arrangement_type,
                "arrangement_label": reservation._get_arrangement_label(reservation.arrangement_type),
                "arrangement_price": arrangement_price,
                "arrangement_product_id": product.id if product else False,
                "arrangement_charged": bool(reservation.arrangement_charged),
                "customer_name": reservation.customer_name,
                "start_datetime": fields.Datetime.to_string(reservation.start_datetime),
                "end_datetime": fields.Datetime.to_string(reservation.end_datetime),
            }
        return snapshot

    @api.model
    def mark_reservation_charged_for_table(self, table_id):
        """Mark the active reservation for a table as having its arrangement charged.

        Returns True if a reservation was found and marked, False otherwise.
        """
        reservation = self._get_active_reservation_for_table(table_id)
        if reservation:
            reservation.sudo().write({"arrangement_charged": True})
            return True
        return False

    @api.model
    def finalize_pos_reservation_for_table(self, table_id):
        reservation = self._get_active_reservation_for_table(table_id)
        if reservation:
            reservation.action_done()
        return bool(reservation)

    def _compute_current_arrangement(self):
        now = fields.Datetime.now()
        for table in self:
            reservation = self._get_active_reservation_for_table(table.id, reference_datetime=now)
            table.current_arrangement = (
                reservation._get_arrangement_label(reservation.arrangement_type) if reservation else ""
            )
