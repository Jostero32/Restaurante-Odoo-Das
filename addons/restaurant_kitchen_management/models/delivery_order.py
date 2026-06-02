from odoo import _, api, fields, models


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
        # Con sudo(): este metodo se dispara tanto desde action_confirm()
        # (usuario interno) como desde create() en pedidos web, donde el
        # contexto puede ser el usuario publico/portal del checkout, sin
        # permiso de lectura sobre sale.order.line ni product.template.
        # Coherente con _compute_product_summary del modelo delivery.
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
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # La sincronizacion masiva de ventas historicas
        # (_sync_delivery_orders_for_existing_sales, ejecutada en cada
        # actualizacion del modulo) crea pedidos delivery 'confirmed' para
        # TODAS las ventas existentes, incluidas las ya completadas. Ese
        # flujo marca skip_delivery_internal_notify=True; lo respetamos para
        # NO inundar el tablero de cocina con pedidos viejos. Un checkout web
        # real NO lleva ese flag, asi que su orden de cocina si se crea.
        if self.env.context.get("skip_delivery_internal_notify"):
            return records
        # Pedidos web: el delivery se crea directamente con state='confirmed'
        # sin pasar por action_confirm(), por lo que hay que disparar
        # _ensure_kitchen_order() aqui si ya viene confirmado.
        auto_kitchen = records.filtered(
            lambda o: o.state in ("confirmed", "assigned", "on_route") and not o.kitchen_order_id
        )
        if auto_kitchen:
            auto_kitchen._ensure_kitchen_order()
        return records

    # ------------------------------------------------------------------
    # State overrides
    # ------------------------------------------------------------------
    def action_confirm(self):
        result = super().action_confirm()
        self._ensure_kitchen_order()
        return result

    def action_cancel(self):
        # Cancelar la orden de cocina asociada (si esta activa) para que
        # la cocina no siga preparando un pedido que ya fue cancelado.
        result = super().action_cancel()
        for order in self:
            kitchen_order = order.kitchen_order_id
            if kitchen_order and kitchen_order.state not in ("served", "cancelled"):
                kitchen_order.sudo().action_cancel()
                order.sudo().message_post(
                    body=_(
                        "Se cancelo automaticamente la orden de cocina %s "
                        "al cancelar el pedido delivery."
                    ) % kitchen_order.name,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
        return result
