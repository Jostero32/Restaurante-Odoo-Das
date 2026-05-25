from odoo import _, fields, models


class RestaurantDeliveryOrder(models.Model):
    _inherit = "restaurant.delivery.order"

    kitchen_order_id = fields.Many2one(
        "restaurant.kitchen.order",
        string="Orden de Cocina",
        copy=False,
        readonly=True,
        help="Orden de cocina generada automaticamente al confirmar el pedido.",
    )
    kitchen_ready = fields.Boolean(
        string="Listo para despacho",
        copy=False,
        readonly=True,
        tracking=True,
        help="Cocina marco el pedido como listo. Puede despacharse al repartidor.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _prepare_kitchen_order_values(self):
        """Construye los valores para crear la orden de cocina desde un delivery."""
        self.ensure_one()
        lines_vals = []
        sale_lines = self.sale_order_id.sudo().order_line.filtered(
            lambda l: not l.display_type
            and l.product_id
            and l.product_id.product_tmpl_id.kitchen_preparable
        )
        for line in sale_lines:
            default_note = line.product_id.product_tmpl_id.kitchen_default_note or ""
            lines_vals.append(
                (0, 0, {
                    "product_id": line.product_id.id,
                    "quantity": line.product_uom_qty,
                    "line_note": default_note,
                })
            )
        return {
            "origin_type": "delivery",
            "delivery_order_id": self.id,
            "sale_order_id": self.sale_order_id.id if self.sale_order_id else False,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "notes": self.notes or "",
            "line_ids": lines_vals,
        }

    def _ensure_kitchen_order(self):
        """Crea la orden de cocina si no existe y hay productos preparables."""
        for order in self:
            if order.kitchen_order_id:
                continue
            values = order._prepare_kitchen_order_values()
            if not values.get("line_ids"):
                # No hay productos preparables: no se crea orden de cocina
                continue
            kitchen_order = self.env["restaurant.kitchen.order"].sudo().create(values)
            order.sudo().write({"kitchen_order_id": kitchen_order.id})
            order.sudo().message_post(
                body=_(
                    "Se creo automaticamente la orden de cocina %s con %s productos preparables."
                ) % (kitchen_order.name, len(values["line_ids"])),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    # ------------------------------------------------------------------
    # State overrides
    # ------------------------------------------------------------------
    def action_confirm(self):
        result = super().action_confirm()
        self._ensure_kitchen_order()
        return result
