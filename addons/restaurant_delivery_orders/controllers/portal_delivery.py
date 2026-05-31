from collections import OrderedDict

from odoo import _, fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools.misc import format_amount


class RestaurantDeliveryPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id.commercial_partner_id
        if "delivery_order_count" in counters:
            values["delivery_order_count"] = request.env["restaurant.delivery.order"].sudo().search_count(
                self._get_delivery_orders_domain(partner=partner)
            )
        if "delivery_invoice_count" in counters or "delivery_invoice_pending_count" in counters:
            invoices = self._get_delivery_invoice_records(partner=partner)
            posted_invoices = invoices.filtered(lambda inv: inv.state == "posted")
            values["delivery_invoice_count"] = len(invoices)
            values["delivery_invoice_pending_count"] = len(
                posted_invoices.filtered(lambda inv: inv.payment_state not in {"paid", "reversed"})
            )
        return values

    def _get_delivery_orders_domain(self, partner=None):
        partner = partner or request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", [partner.id])]

    def _get_delivery_invoice_domain(self, partner=None):
        partner = partner or request.env.user.partner_id.commercial_partner_id
        sale_orders = request.env["sale.order"].sudo().search(
            [
                ("delivery_order_id", "!=", False),
                ("delivery_order_id.partner_id", "child_of", [partner.id]),
            ]
        )
        invoice_ids = sale_orders.mapped("invoice_ids").ids
        if not invoice_ids:
            return [("id", "=", 0)]
        return [
            ("id", "in", invoice_ids),
            ("move_type", "in", ["out_invoice", "out_receipt"]),
            ("state", "!=", "cancel"),
        ]

    def _get_delivery_invoice_records(self, partner=None):
        return request.env["account.move"].sudo().search(self._get_delivery_invoice_domain(partner=partner))

    def _get_delivery_portal_metrics(self, partner=None):
        partner = partner or request.env.user.partner_id.commercial_partner_id
        delivery_orders = request.env["restaurant.delivery.order"].sudo().search(
            self._get_delivery_orders_domain(partner=partner)
        )
        invoices = self._get_delivery_invoice_records(partner=partner)
        posted_invoices = invoices.filtered(lambda inv: inv.state == "posted")
        pending_invoices = posted_invoices.filtered(
            lambda inv: inv.payment_state not in {"paid", "reversed"}
        )
        paid_invoices = posted_invoices.filtered(lambda inv: inv.payment_state in {"paid", "reversed"})
        pending_amount = sum(pending_invoices.mapped("amount_residual")) if pending_invoices else 0.0
        total_amount = sum(posted_invoices.mapped("amount_total")) if posted_invoices else 0.0
        return {
            "orders_total": len(delivery_orders),
            "orders_active": len(
                delivery_orders.filtered(lambda order: order.state in {"draft", "confirmed", "assigned", "on_route"})
            ),
            "orders_delivered": len(delivery_orders.filtered(lambda order: order.state == "delivered")),
            "invoice_total": len(invoices),
            "invoice_posted": len(posted_invoices),
            "invoice_pending": len(pending_invoices),
            "invoice_paid": len(paid_invoices),
            "invoice_pending_amount": pending_amount,
            "invoice_pending_amount_display": format_amount(
                request.env, pending_amount, request.env.company.currency_id
            ),
            "invoice_total_amount_display": format_amount(
                request.env, total_amount, request.env.company.currency_id
            ),
        }

    def _get_delivery_searchbar_sortings(self):
        return {
            "date": {"label": _("Mas recientes"), "order": "order_datetime desc, id desc"},
            "eta": {"label": _("ETA mas bajo"), "order": "eta_minutes asc, order_datetime desc"},
            "status": {"label": _("Estado"), "order": "state asc, order_datetime desc"},
        }

    def _get_delivery_searchbar_filters(self):
        return {
            "all": {"label": _("Todos"), "domain": []},
            "preparing": {"label": _("En preparacion"), "domain": [("state", "in", ["draft", "confirmed", "assigned"])]},
            "on_route": {"label": _("En camino"), "domain": [("state", "=", "on_route")]},
            "delivered": {"label": _("Entregados"), "domain": [("state", "=", "delivered")]},
            "issues": {"label": _("Con incidencias"), "domain": [("incident_ids", "!=", False)]},
        }

    def _get_delivery_state_class(self, state_or_key):
        return {
            "scheduled_received": "primary",
            "draft": "info",
            "confirmed": "info",
            "assigned": "info",
            "on_route": "warning",
            "delivered": "success",
            "cancelled": "dark",
        }.get(state_or_key, "secondary")

    def _get_delivery_state_label(self, state_or_key):
        return {
            "scheduled_received": _("Pedido recibido"),
            "draft": _("En preparacion"),
            "confirmed": _("En preparacion"),
            "assigned": _("En preparacion"),
            "on_route": _("En camino"),
            "delivered": _("Entregado"),
            "cancelled": _("Cancelado"),
        }.get(state_or_key, _("En proceso"))

    def _get_delivery_invoice_searchbar_sortings(self):
        return {
            "date": {"label": _("Mas recientes"), "order": "invoice_date desc, create_date desc, id desc"},
            "due": {"label": _("Vencimiento"), "order": "invoice_date_due asc, invoice_date desc"},
            "amount": {"label": _("Mayor importe"), "order": "amount_total desc, invoice_date desc"},
            "status": {"label": _("Estado"), "order": "state asc, payment_state asc, invoice_date desc"},
        }

    def _get_delivery_invoice_searchbar_filters(self):
        today = fields.Date.today()
        return {
            "all": {"label": _("Todas"), "domain": []},
            "draft": {"label": _("Borrador"), "domain": [("state", "=", "draft")]},
            "pending": {
                "label": _("Pendientes"),
                "domain": [("state", "=", "posted"), ("payment_state", "in", ["not_paid", "partial", "in_payment"])],
            },
            "paid": {"label": _("Pagadas"), "domain": [("state", "=", "posted"), ("payment_state", "in", ["paid", "reversed"])]},
            "overdue": {
                "label": _("Vencidas"),
                "domain": [
                    ("state", "=", "posted"),
                    ("payment_state", "in", ["not_paid", "partial", "in_payment"]),
                    ("invoice_date_due", "!=", False),
                    ("invoice_date_due", "<", today),
                ],
            },
        }

    def _get_delivery_invoice_state_label(self, invoice):
        if invoice.state == "draft":
            return _("Borrador")
        if invoice.state != "posted":
            return _("En proceso")
        if invoice.payment_state in {"paid", "reversed"}:
            return _("Pagada")
        if invoice.payment_state in {"partial", "in_payment"}:
            return _("Pago parcial")
        return _("Pendiente de pago")

    def _get_delivery_invoice_state_class(self, invoice):
        if invoice.state == "draft":
            return "secondary"
        if invoice.state != "posted":
            return "info"
        if invoice.payment_state in {"paid", "reversed"}:
            return "success"
        if invoice.payment_state in {"partial", "in_payment"}:
            return "warning"
        return "danger"

    def _prepare_delivery_invoice_portal_dict(self, invoice):
        fee_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.sale_line_ids.filtered(lambda sale_line: sale_line.is_delivery_fee)
        )
        food_lines = invoice.invoice_line_ids.filtered(lambda line: not line.display_type) - fee_lines
        related_delivery_orders = (
            invoice.invoice_line_ids.sale_line_ids.order_id.mapped("delivery_order_id").filtered(lambda order: order)
        )
        is_pending = invoice.state == "posted" and invoice.payment_state not in {"paid", "reversed"}
        is_overdue = bool(
            is_pending and invoice.invoice_date_due and invoice.invoice_date_due < fields.Date.today()
        )
        return {
            "record": invoice,
            "state_label": self._get_delivery_invoice_state_label(invoice),
            "state_class": self._get_delivery_invoice_state_class(invoice),
            "food_subtotal": sum(food_lines.mapped("price_subtotal")) if food_lines else 0.0,
            "delivery_fee": sum(fee_lines.mapped("price_subtotal")) if fee_lines else 0.0,
            "invoice_total": invoice.amount_total,
            "is_pending": is_pending,
            "is_overdue": is_overdue,
            "related_delivery_orders": related_delivery_orders,
            "detail_url": f"/my/delivery/invoices/{invoice.id}",
            "pdf_url": invoice.get_portal_url(report_type="pdf", download=True),
        }

    def _get_delivery_progress_steps(self, order):
        is_scheduled_received = order.display_state_key == "scheduled_received"
        sequence = (
            ["received", "preparing", "on_route", "delivered"]
            if is_scheduled_received or order.is_scheduled
            else ["preparing", "on_route", "delivered"]
        )
        progress_state = {
            "scheduled_received": "received",
            "draft": "preparing",
            "confirmed": "preparing",
            "assigned": "preparing",
            "on_route": "on_route",
            "delivered": "delivered",
        }.get(order.display_state_key)
        # Cuando ya pasamos de "Recibido" a operativo en pedido programado, "received" queda hecho.
        if order.is_scheduled and progress_state != "received" and "received" in sequence:
            pass  # logica abajo marca done por indice
        current_index = sequence.index(progress_state) if progress_state in sequence else -1
        labels = {
            "received": _("Recibido"),
            "preparing": _("En preparacion"),
            "on_route": _("En camino"),
            "delivered": _("Entregado"),
        }
        steps = []
        for index, state_key in enumerate(sequence):
            steps.append(
                {
                    "key": state_key,
                    "label": labels[state_key],
                    "done": current_index >= index,
                    "current": current_index == index,
                }
            )
        if order.state == "cancelled":
            steps.append({"key": "cancelled", "label": _("Pedido cancelado"), "done": True, "current": True})
        return steps

    def _prepare_delivery_order_portal_dict(self, order):
        posted_invoices = order.linked_invoice_ids.filtered(lambda inv: inv.state == "posted")
        display_key = order.display_state_key
        return {
            "record": order,
            "state_label": self._get_delivery_state_label(display_key),
            "state_class": self._get_delivery_state_class(display_key),
            "invoice_posted_count": len(posted_invoices),
            "invoice_unpaid_count": len(
                posted_invoices.filtered(lambda inv: inv.payment_state not in {"paid", "reversed"})
            ),
            "progress_steps": self._get_delivery_progress_steps(order),
            "is_scheduled": bool(order.is_scheduled and order.scheduled_for),
            "is_scheduled_received": display_key == "scheduled_received",
            "scheduled_for_display": order.scheduled_for_display or "",
        }

    @http.route(
        ["/my/delivery", "/my/delivery/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_delivery_orders(
        self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw
    ):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id.commercial_partner_id
        DeliveryOrder = request.env["restaurant.delivery.order"].sudo()
        domain = self._get_delivery_orders_domain(partner=partner)

        searchbar_sortings = self._get_delivery_searchbar_sortings()
        if not sortby:
            sortby = "date"
        order_by = searchbar_sortings[sortby]["order"]

        searchbar_filters = self._get_delivery_searchbar_filters()
        if not filterby:
            filterby = "all"
        domain += searchbar_filters[filterby]["domain"]

        if date_begin and date_end:
            domain += [("create_date", ">", date_begin), ("create_date", "<=", date_end)]

        pager = portal_pager(
            url="/my/delivery",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "filterby": filterby,
            },
            total=DeliveryOrder.search_count(domain),
            page=page,
            step=20,
        )

        orders = DeliveryOrder.search(
            domain,
            order=order_by,
            limit=20,
            offset=pager["offset"],
        )
        request.session["my_delivery_orders_history"] = orders.ids[:100]

        values.update(
            {
                "date": date_begin,
                "delivery_portal_metrics": self._get_delivery_portal_metrics(partner=partner),
                "delivery_orders": [self._prepare_delivery_order_portal_dict(order) for order in orders],
                "page_name": "delivery_order",
                "pager": pager,
                "default_url": "/my/delivery",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby,
            }
        )
        return request.render("restaurant_delivery_orders.portal_my_delivery_orders", values)

    @http.route(
        ["/my/delivery/invoices", "/my/delivery/invoices/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_delivery_invoices(
        self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw
    ):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id.commercial_partner_id
        AccountMove = request.env["account.move"].sudo()
        domain = self._get_delivery_invoice_domain(partner=partner)

        searchbar_sortings = self._get_delivery_invoice_searchbar_sortings()
        if not sortby:
            sortby = "date"
        order_by = searchbar_sortings[sortby]["order"]

        searchbar_filters = self._get_delivery_invoice_searchbar_filters()
        if not filterby:
            filterby = "all"
        domain += searchbar_filters[filterby]["domain"]

        if date_begin and date_end:
            domain += [("create_date", ">", date_begin), ("create_date", "<=", date_end)]

        pager = portal_pager(
            url="/my/delivery/invoices",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "filterby": filterby,
            },
            total=AccountMove.search_count(domain),
            page=page,
            step=20,
        )
        invoices = AccountMove.search(domain, order=order_by, limit=20, offset=pager["offset"])
        request.session["my_delivery_invoice_history"] = invoices.ids[:100]

        values.update(
            {
                "date": date_begin,
                "delivery_portal_metrics": self._get_delivery_portal_metrics(partner=partner),
                "delivery_invoice_rows": [self._prepare_delivery_invoice_portal_dict(inv) for inv in invoices],
                "page_name": "delivery_invoice",
                "pager": pager,
                "default_url": "/my/delivery/invoices",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby,
            }
        )
        return request.render("restaurant_delivery_orders.portal_my_delivery_invoices", values)

    @http.route(["/my/delivery/invoices/<int:invoice_id>"], type="http", auth="user", website=True)
    def portal_my_delivery_invoice_detail(self, invoice_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        invoice = request.env["account.move"].sudo().search(
            self._get_delivery_invoice_domain(partner=partner) + [("id", "=", invoice_id)],
            limit=1,
        )
        if not invoice:
            return request.redirect("/my/delivery/invoices")

        values = self._prepare_portal_layout_values()
        invoice_data = self._prepare_delivery_invoice_portal_dict(invoice)
        values.update(
            {
                "delivery_portal_metrics": self._get_delivery_portal_metrics(partner=partner),
                "delivery_invoice_data": invoice_data,
                "delivery_invoice": invoice,
                "delivery_invoice_orders": invoice_data.get("related_delivery_orders"),
                "page_name": "delivery_invoice",
            }
        )
        values = self._get_page_view_values(
            invoice,
            False,
            values,
            "my_delivery_invoice_history",
            False,
            **kw,
        )
        return request.render("restaurant_delivery_orders.portal_delivery_invoice_page", values)

    @http.route(["/my/delivery/<int:order_id>"], type="http", auth="public", website=True)
    def portal_my_delivery_order_detail(self, order_id, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access("restaurant.delivery.order", order_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")

        values = self._prepare_portal_layout_values()
        values.update(
            {
                "delivery_order_data": self._prepare_delivery_order_portal_dict(order_sudo),
                "delivery_order": order_sudo,
                "invoice_rows": [
                    self._prepare_delivery_invoice_portal_dict(inv)
                    for inv in order_sudo.linked_invoice_ids.sorted(
                        key=lambda inv: inv.invoice_date or inv.create_date,
                        reverse=True,
                    )
                ],
                "incidents": order_sudo.incident_ids.sudo(),
                "incident_submitted": kw.get("incident_submitted"),
                "incident_error": kw.get("incident_error"),
                "reorder_added": kw.get("reorder_added"),
                "reorder_skipped": kw.get("reorder_skipped"),
                "reorder_empty": kw.get("reorder_empty"),
                "rating_submitted": kw.get("rating_submitted"),
                "rating_error": kw.get("rating_error"),
                "page_name": "delivery_order",
            }
        )
        values = self._get_page_view_values(
            order_sudo,
            access_token,
            values,
            "my_delivery_orders_history",
            False,
            **kw,
        )
        return request.render("restaurant_delivery_orders.portal_delivery_order_page", values)

    @http.route(
        ["/my/delivery/<int:order_id>/rate"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_rate_delivery(self, order_id, **post):
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env["restaurant.delivery.order"].sudo().search(
            [("id", "=", order_id), ("partner_id", "child_of", [partner.id])],
            limit=1,
        )
        if not order:
            return request.redirect("/my/delivery")
        if order.state != "delivered":
            return request.redirect(f"/my/delivery/{order.id}?rating_error=state")
        if order.has_rating:
            return request.redirect(f"/my/delivery/{order.id}?rating_error=duplicate")

        score = (post.get("score") or "").strip()
        if score not in {"1", "2", "3", "4", "5"}:
            return request.redirect(f"/my/delivery/{order.id}?rating_error=invalid")
        comment = (post.get("comment") or "").strip() or False

        request.env["restaurant.delivery.rating"].sudo().create(
            {
                "delivery_order_id": order.id,
                "partner_id": partner.id,
                "driver_id": order.driver_id.id or False,
                "score": score,
                "comment": comment,
            }
        )
        order.sudo().message_post(
            body=request.env._(
                "Calificacion del cliente: %s estrellas%s"
            ) % (score, (" - %s" % comment) if comment else ""),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return request.redirect(f"/my/delivery/{order.id}?rating_submitted=1#delivery-rating")

    @http.route(
        ["/my/delivery/<int:order_id>/reorder"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_reorder_delivery(self, order_id, **post):
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env["restaurant.delivery.order"].sudo().search(
            [("id", "=", order_id), ("partner_id", "child_of", [partner.id])],
            limit=1,
        )
        if not order or not order.sale_order_id:
            return request.redirect("/my/delivery")
        if order.state not in {"delivered", "cancelled"}:
            return request.redirect(f"/my/delivery/{order.id}")

        source_lines = order.sale_order_id.order_line.filtered(
            lambda line: not line.display_type
            and not line.is_delivery_fee
            and not getattr(line, "is_delivery", False)
            and line.product_id
        )
        if not source_lines:
            return request.redirect(f"/my/delivery/{order.id}?reorder_empty=1")

        website = request.website
        cart = website.sale_get_order(force_create=True)
        added_count = 0
        skipped_count = 0
        for line in source_lines:
            product = line.product_id.with_context(website_sale_force_publish=False)
            try:
                if not product.exists() or not product.sale_ok:
                    skipped_count += 1
                    continue
                if hasattr(product, "is_published") and not product.sudo().is_published:
                    skipped_count += 1
                    continue
                qty_to_add = int(line.product_uom_qty or 1)
                if qty_to_add <= 0:
                    qty_to_add = 1
                cart.with_context(website_id=website.id)._cart_update(
                    product_id=product.id,
                    add_qty=qty_to_add,
                )
                added_count += 1
            except Exception:
                skipped_count += 1
                continue

        if added_count == 0:
            return request.redirect(f"/my/delivery/{order.id}?reorder_empty=1")
        params = f"reorder_added={added_count}"
        if skipped_count:
            params += f"&reorder_skipped={skipped_count}"
        return request.redirect(f"/shop/cart?{params}")

    @http.route(
        ["/my/delivery/<int:order_id>/incident"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_submit_delivery_incident(self, order_id, **post):
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env["restaurant.delivery.order"].sudo().search(
            [("id", "=", order_id), ("partner_id", "child_of", [partner.id])],
            limit=1,
        )
        if not order:
            return request.redirect("/my/delivery")

        issue_type = (post.get("issue_type") or "").strip()
        description = (post.get("description") or "").strip()
        allowed_issue_types = {"incomplete", "cold", "delay", "wrong_item", "other"}

        if issue_type not in allowed_issue_types or len(description) < 10:
            return request.redirect(
                f"/my/delivery/{order.id}?access_token={order._portal_ensure_token()}&incident_error=1#delivery-incidents"
            )

        request.env["restaurant.delivery.incident"].sudo().create(
            {
                "delivery_order_id": order.id,
                "partner_id": order.partner_id.id or partner.id,
                "issue_type": issue_type,
                "description": description,
            }
        )
        return request.redirect(
            f"/my/delivery/{order.id}?access_token={order._portal_ensure_token()}&incident_submitted=1#delivery-incidents"
        )
