from odoo import _, api, fields, models


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

    def _get_customer_invoice_documents(self):
        self.ensure_one()
        return self.invoice_ids.filtered(
            lambda inv: inv.move_type in {"out_invoice", "out_receipt"} and inv.state != "cancel"
        )

    def _is_delivery_invoice_candidate(self):
        self.ensure_one()
        if self.state == "sale":
            return True
        if self.website_id and self.state == "sent":
            has_lines = bool(self.website_order_line.filtered(lambda line: not line.display_type))
            return has_lines
        return False

    def action_ensure_invoice(self):
        AccountMove = self.env["account.move"]
        created_invoices = AccountMove
        for order in self:
            if not order._is_delivery_invoice_candidate():
                continue
            if order._get_customer_invoice_documents():
                continue
            invoices = order.with_context(raise_if_nothing_to_invoice=False)._create_invoices()
            created_invoices |= invoices.filtered(
                lambda inv: inv.move_type in {"out_invoice", "out_receipt"} and inv.state != "cancel"
            )
        return created_invoices

    def _ensure_delivery_sale_confirmed(self):
        for order in self:
            if order.state not in {"draft", "sent"}:
                continue
            has_real_lines = bool(order.order_line.filtered(lambda line: not line.display_type))
            if not has_real_lines:
                continue
            order.action_confirm()

    def action_finalize_delivery_invoicing(self):
        customer_invoice_types = {"out_invoice", "out_receipt"}
        candidate_orders = self.filtered(lambda order: order.state != "cancel")
        if not candidate_orders:
            return self.env["account.move"]

        candidate_orders._ensure_delivery_sale_confirmed()
        candidate_orders._ensure_fixed_delivery_fee_line()
        candidate_orders.action_ensure_invoice()

        customer_invoices = candidate_orders.mapped("invoice_ids").filtered(
            lambda inv: inv.move_type in customer_invoice_types and inv.state != "cancel"
        )
        draft_invoices = customer_invoices.filtered(lambda inv: inv.state == "draft")
        if draft_invoices:
            draft_invoices.action_post()

        posted_unsent_invoices = customer_invoices.filtered(
            lambda inv: inv.state == "posted" and not inv.is_move_sent
        )
        sendable_invoices = posted_unsent_invoices.filtered(
            lambda inv: inv.partner_id.email or inv.commercial_partner_id.email
        )
        if sendable_invoices:
            self.env["account.move.send"]._generate_and_send_invoices(
                sendable_invoices,
                allow_raising=False,
                allow_fallback_pdf=True,
                sending_methods={"email"},
            )
        return customer_invoices

    @api.model
    def _get_delivery_invoice_backfill_scope(self):
        active_ids = self.env.context.get("active_ids") or []
        if active_ids:
            return self.browse(active_ids).exists()
        return self.search(
            [
                ("state", "in", ["sale", "sent"]),
                "|",
                ("delivery_order_id", "!=", False),
                ("website_id", "!=", False),
            ]
        )

    def action_backfill_delivery_missing_invoices(self):
        scope_orders = self.exists() if self else self._get_delivery_invoice_backfill_scope()
        scoped_delivery_orders = scope_orders.filtered(
            lambda order: order.state in {"sale", "sent"} and (order.delivery_order_id or order.website_id)
        )
        invoice_candidates = scoped_delivery_orders.filtered(
            lambda order: order._is_delivery_invoice_candidate()
        )
        missing_before = invoice_candidates.filtered(
            lambda order: not order._get_customer_invoice_documents()
        )
        created_invoices = missing_before.action_ensure_invoice()
        missing_after = missing_before.filtered(
            lambda order: not order._get_customer_invoice_documents()
        )

        created_orders_count = len(missing_before) - len(missing_after)
        already_invoiced_count = len(invoice_candidates) - len(missing_before)
        ignored_count = len(scope_orders) - len(invoice_candidates)
        warning_count = len(missing_after)

        notification_type = "success" if created_orders_count or not warning_count else "warning"
        message = _(
            "Facturas creadas: %(created_orders)s pedidos (%(created_invoices)s documentos). "
            "Ya facturados: %(already)s. Ignorados: %(ignored)s. Pendientes: %(pending)s."
        ) % {
            "created_orders": created_orders_count,
            "created_invoices": len(created_invoices),
            "already": already_invoiced_count,
            "ignored": ignored_count,
            "pending": warning_count,
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Backfill de facturas delivery"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }

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
            order.action_ensure_invoice()
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
