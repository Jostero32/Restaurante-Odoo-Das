from collections import OrderedDict

from odoo import _, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request


class RestaurantDeliveryPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "delivery_order_count" in counters:
            partner = request.env.user.partner_id.commercial_partner_id
            delivery_count = request.env["restaurant.delivery.order"].sudo().search_count(
                self._get_delivery_orders_domain(partner=partner)
            )
            values["delivery_order_count"] = delivery_count
        return values

    def _get_delivery_orders_domain(self, partner=None):
        partner = partner or request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", [partner.id])]

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

    def _get_delivery_state_class(self, state):
        return {
            "draft": "info",
            "confirmed": "info",
            "assigned": "info",
            "on_route": "warning",
            "delivered": "success",
            "cancelled": "dark",
        }.get(state, "secondary")

    def _get_delivery_state_label(self, state):
        return {
            "draft": _("En preparacion"),
            "confirmed": _("En preparacion"),
            "assigned": _("En preparacion"),
            "on_route": _("En camino"),
            "delivered": _("Entregado"),
            "cancelled": _("Cancelado"),
        }.get(state, _("En proceso"))

    def _get_delivery_progress_steps(self, order):
        progress_state = {
            "draft": "preparing",
            "confirmed": "preparing",
            "assigned": "preparing",
            "on_route": "on_route",
            "delivered": "delivered",
        }.get(order.state)
        sequence = ["preparing", "on_route", "delivered"]
        current_index = sequence.index(progress_state) if progress_state in sequence else -1
        steps = []
        labels = {
            "preparing": _("En preparacion"),
            "on_route": _("En camino"),
            "delivered": _("Entregado"),
        }
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
        return {
            "record": order,
            "state_label": self._get_delivery_state_label(order.state),
            "state_class": self._get_delivery_state_class(order.state),
            "invoice_posted_count": len(posted_invoices),
            "invoice_unpaid_count": len(
                posted_invoices.filtered(lambda inv: inv.payment_state not in {"paid", "reversed"})
            ),
            "progress_steps": self._get_delivery_progress_steps(order),
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
        DeliveryOrder = request.env["restaurant.delivery.order"].sudo()
        domain = self._get_delivery_orders_domain()

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
                "invoice_rows": order_sudo.linked_invoice_ids.sorted(
                    key=lambda inv: inv.invoice_date or inv.create_date, reverse=True
                ),
                "incidents": order_sudo.incident_ids.sudo(),
                "incident_submitted": kw.get("incident_submitted"),
                "incident_error": kw.get("incident_error"),
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
