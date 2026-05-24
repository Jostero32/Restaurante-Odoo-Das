from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_order_id = fields.Many2one(
        "restaurant.delivery.order",
        string="Pedido delivery",
        copy=False,
        readonly=True,
    )

    def _format_delivery_address(self):
        self.ensure_one()
        shipping_partner = self.partner_shipping_id or self.partner_id
        return shipping_partner.contact_address or shipping_partner.display_name

    def _map_sale_state_to_delivery_state(self, current_delivery_state=None):
        self.ensure_one()
        if self.state == "cancel":
            return "cancelled"
        if self.state == "sent":
            return "confirmed"
        if current_delivery_state in {"assigned", "on_route", "delivered"}:
            return current_delivery_state
        if current_delivery_state == "cancelled":
            return "cancelled"
        return "confirmed"

    def _is_delivery_sync_candidate(self):
        self.ensure_one()
        if self.state in {"sale", "cancel"}:
            return True
        # En ecommerce, "sent" equivale a pedido confirmado en checkout
        # aunque el pago pueda seguir en proceso.
        if self.website_id and self.state == "sent":
            has_lines = bool(self.website_order_line.filtered(lambda line: not line.display_type))
            return has_lines
        return False

    def _requires_fixed_delivery_fee(self):
        self.ensure_one()
        return bool(self.website_id) and self.state in {"sent", "sale", "cancel"}

    def _ensure_fixed_delivery_fee_line(self):
        SaleOrderLine = self.env["sale.order.line"]
        for order in self:
            if not order._requires_fixed_delivery_fee():
                continue

            company = order.company_id
            fee_amount = company.delivery_fixed_fee or 0.0
            fee_product = company.delivery_fee_product_id or company._get_or_create_delivery_fee_product()
            if not fee_product:
                continue

            fee_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.is_delivery_fee
            )
            if fee_amount <= 0:
                fee_lines.with_context(skip_delivery_line_sync=True).unlink()
                continue

            product_taxes = fee_product.taxes_id.filtered(
                lambda tax: not tax.company_id or tax.company_id == order.company_id
            )
            line_vals = {
                "name": fee_product.with_context(lang=order.partner_id.lang).get_product_multiline_description_sale(),
                "product_id": fee_product.id,
                "product_uom_qty": 1.0,
                "product_uom": fee_product.uom_id.id,
                "price_unit": fee_amount,
                "tax_id": [(6, 0, product_taxes.ids)],
                "is_delivery_fee": True,
            }
            if fee_lines:
                main_line = fee_lines[0]
                main_line.with_context(skip_delivery_line_sync=True).write(line_vals)
                if len(fee_lines) > 1:
                    fee_lines[1:].with_context(skip_delivery_line_sync=True).unlink()
            else:
                line_vals["order_id"] = order.id
                SaleOrderLine.with_context(skip_delivery_line_sync=True).create(line_vals)

    def _prepare_delivery_order_vals(self, current_delivery_order=None):
        self.ensure_one()
        shipping_partner = self.partner_shipping_id or self.partner_id
        commercial_partner = self.partner_id.commercial_partner_id
        customer_phone = (
            shipping_partner.mobile
            or shipping_partner.phone
            or commercial_partner.mobile
            or commercial_partner.phone
            or False
        )
        eta_minutes = current_delivery_order.eta_minutes if current_delivery_order else 35
        mapped_state = self._map_sale_state_to_delivery_state(
            current_delivery_order.state if current_delivery_order else None
        )

        return {
            "customer_name": shipping_partner.name or commercial_partner.name,
            "partner_id": commercial_partner.id,
            "customer_phone": customer_phone,
            "delivery_address": self._format_delivery_address(),
            "order_datetime": self.date_order or fields.Datetime.now(),
            "eta_minutes": eta_minutes,
            "amount_total": self.amount_total,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "notes": self.note or "",
            "sale_order_id": self.id,
            "state": mapped_state,
        }

    def _sync_delivery_order_from_sale(self):
        DeliveryOrder = self.env["restaurant.delivery.order"]
        for order in self:
            if not order._is_delivery_sync_candidate():
                continue
            order._ensure_fixed_delivery_fee_line()
            delivery_order = order.delivery_order_id or DeliveryOrder.search(
                [("sale_order_id", "=", order.id)], limit=1
            )
            vals = order._prepare_delivery_order_vals(delivery_order)
            if delivery_order:
                delivery_order.write(vals)
            else:
                delivery_order = DeliveryOrder.create(vals)
            if order.delivery_order_id != delivery_order:
                order.with_context(skip_delivery_sync=True).write(
                    {"delivery_order_id": delivery_order.id}
                )

    @api.model
    def _sync_delivery_orders_for_existing_sales(self):
        sales = self.search(
            [
                "|",
                ("state", "in", ["sale", "cancel"]),
                "&",
                ("website_id", "!=", False),
                ("state", "=", "sent"),
            ]
        )
        sales.with_context(
            skip_delivery_customer_notify=True,
            skip_delivery_internal_notify=True,
        )._sync_delivery_order_from_sale()

    def action_confirm(self):
        result = super().action_confirm()
        self._ensure_fixed_delivery_fee_line()
        self._sync_delivery_order_from_sale()
        return result

    def _action_cancel(self):
        result = super()._action_cancel()
        self._sync_delivery_order_from_sale()
        return result

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_delivery_sync"):
            return result
        tracked_fields = {
            "state",
            "website_id",
            "partner_id",
            "partner_shipping_id",
            "date_order",
            "amount_total",
            "currency_id",
            "note",
        }
        if tracked_fields.intersection(vals):
            self._ensure_fixed_delivery_fee_line()
            self._sync_delivery_order_from_sale()
        return result

    def action_open_delivery_order(self):
        self.ensure_one()
        if not self.delivery_order_id:
            return False
        action = self.env["ir.actions.actions"]._for_xml_id(
            "restaurant_delivery_orders.action_restaurant_delivery_orders"
        )
        action["view_mode"] = "form"
        action["views"] = [
            (self.env.ref("restaurant_delivery_orders.view_restaurant_delivery_order_form").id, "form")
        ]
        action["res_id"] = self.delivery_order_id.id
        action["target"] = "current"
        return action
