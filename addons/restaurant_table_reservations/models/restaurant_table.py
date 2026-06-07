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
        """Allow domain filters like [('zone', '=', 'main')] or [('zone', 'in', ['main','patio'])]."""
        if isinstance(value, (list, tuple, set)):
            wanted_zones = set(value)
        else:
            wanted_zones = {value}

        floors = self.env["restaurant.floor"].sudo().search([])
        floor_ids = []
        for floor in floors:
            fname = (floor.name or "").strip().lower()
            if "interior" in fname and "main" in wanted_zones:
                floor_ids.append(floor.id)
            elif "patio" in fname and "patio" in wanted_zones:
                floor_ids.append(floor.id)
        if operator in ("=", "in"):
            return [("floor_id", "in", floor_ids)]
        if operator in ("!=", "not in"):
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
                "|",
                ("state", "in", ("confirmed", "seated")),
                "&",
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
                "|",
                ("state", "in", ("confirmed", "seated")),
                "&",
                ("start_datetime", "<=", now),
                ("end_datetime", ">=", now),
            ]
        )
        snapshot = {}
        for reservation in reservations:
            arrangement_price = reservation._get_arrangement_cost()
            # Prefer arrangement_product_id; fall back to legacy code_map
            product_product = self.env["product.product"]
            if reservation.arrangement_product_id:
                product_product = self.env["product.product"].sudo().search(
                    [("product_tmpl_id", "=", reservation.arrangement_product_id.id)], limit=1
                )
            elif reservation.arrangement_type and reservation.arrangement_type != "none":
                code_map = {
                    "birthday": "ARR-BIRTHDAY",
                    "anniversary": "ARR-ANNIV",
                    "romantic": "ARR-ROMANTIC",
                    "general": "ARR-GENERAL",
                }
                code = code_map.get(reservation.arrangement_type, "")
                if code:
                    product_product = self.env["product.product"].sudo().search(
                        [("default_code", "=", code)], limit=1
                    )
            arrangement_label = (
                reservation._get_arrangement_label(product=reservation.arrangement_product_id)
                if reservation.arrangement_product_id
                else reservation._get_arrangement_label(reservation.arrangement_type)
            )
            snapshot[reservation.table_id.id] = {
                "reservation_id": reservation.id,
                "table_id": reservation.table_id.id,
                "state": reservation.state,
                "arrangement_type": reservation.arrangement_type,
                "arrangement_label": arrangement_label,
                "arrangement_price": arrangement_price,
                "arrangement_product_id": product_product.id if product_product else False,
                "arrangement_charged": bool(reservation.arrangement_charged),
                "customer_name": reservation.customer_name,
                "start_datetime": fields.Datetime.to_string(reservation.start_datetime),
                "end_datetime": fields.Datetime.to_string(reservation.end_datetime),
            }
        return snapshot

    @api.model
    def mark_reservation_charged_for_table(self, table_id):
        """Inject the arrangement line into the open POS order for the table.

        Only touches POS orders in 'draft' state to avoid contaminating
        finalized/invoiced orders. Returns True if reservation was found.
        """
        reservation = self._get_active_reservation_for_table(table_id)
        if not reservation:
            return False

        # Prefer arrangement_product_id; fall back to legacy code_map
        if reservation.arrangement_product_id:
            product = self.env["product.product"].sudo().search(
                [("product_tmpl_id", "=", reservation.arrangement_product_id.id)], limit=1
            )
        elif reservation.arrangement_type and reservation.arrangement_type != "none":
            code_map = {
                "birthday": "ARR-BIRTHDAY",
                "anniversary": "ARR-ANNIV",
                "romantic": "ARR-ROMANTIC",
                "general": "ARR-GENERAL",
            }
            default_code = code_map.get(reservation.arrangement_type, "")
            product = (
                self.env["product.product"].sudo().search([("default_code", "=", default_code)], limit=1)
                if default_code
                else self.env["product.product"]
            )
        else:
            product = self.env["product.product"]

        open_pos_order = self.env["pos.order"].sudo().search(
            [("table_id", "=", table_id), ("state", "=", "draft")],
            order="id desc",
            limit=1,
        )

        if open_pos_order and product:
            already = open_pos_order.lines.filtered(lambda l: l.product_id.id == product.id)
            if not already:
                price_unit = reservation._get_arrangement_cost()
                tax_ids = product.taxes_id.filtered_domain(
                    self.env["account.tax"]._check_company_domain(open_pos_order.company_id)
                )
                if open_pos_order.fiscal_position_id:
                    tax_ids = open_pos_order.fiscal_position_id.map_tax(tax_ids)
                currency = open_pos_order.currency_id or self.env.company.currency_id
                tax_result = tax_ids.compute_all(
                    price_unit, currency, 1.0,
                    product=product, partner=open_pos_order.partner_id,
                )
                self.env["pos.order.line"].sudo().create({
                    "order_id": open_pos_order.id,
                    "product_id": product.id,
                    "qty": 1.0,
                    "price_unit": price_unit,
                    "tax_ids": [(6, 0, tax_ids.ids)],
                    "price_subtotal": tax_result["total_excluded"],
                    "price_subtotal_incl": tax_result["total_included"],
                })

        reservation.sudo().write({"arrangement_charged": True})
        reservation._notify_pos_reservation_change([reservation.table_id.id])
        return True

    @api.model
    def finalize_pos_reservation_for_table(self, table_id):
        reservation = self._get_active_reservation_for_table(table_id)
        if reservation:
            reservation.action_done()
        return bool(reservation)

    def action_seated(self):
        # action_seated is implemented on the reservation model; keep placeholder for compatibility
        return True

    def _compute_current_arrangement(self):
        now = fields.Datetime.now()
        for table in self:
            reservation = self._get_active_reservation_for_table(table.id, reference_datetime=now)
            if not reservation:
                table.current_arrangement = ""
            elif reservation.arrangement_product_id:
                table.current_arrangement = reservation._get_arrangement_label(
                    product=reservation.arrangement_product_id
                )
            else:
                table.current_arrangement = reservation._get_arrangement_label(reservation.arrangement_type)
