from collections import OrderedDict

from odoo import _, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request


class ReservationCustomerPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "reservation_count" in counters:
            partner = request.env.user.partner_id.commercial_partner_id
            values["reservation_count"] = request.env["restaurant.table.reservation"].sudo().search_count(
                self._get_reservation_domain(partner)
            )
        return values

    def _get_reservation_domain(self, partner=None):
        partner = partner or request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", [partner.id])]

    def _reservation_searchbar_sortings(self):
        return {
            "date_desc": {"label": _("Mas recientes"), "order": "start_datetime desc, id desc"},
            "date_asc": {"label": _("Proximas primero"), "order": "start_datetime asc, id desc"},
            "state": {"label": _("Estado"), "order": "state asc, start_datetime desc"},
        }

    def _reservation_searchbar_filters(self):
        return {
            "all": {"label": _("Todas"), "domain": []},
            "active": {"label": _("Activas"), "domain": [("state", "in", ("draft", "confirmed", "seated"))]},
            "history": {"label": _("Historial"), "domain": [("state", "in", ("done", "cancelled"))]},
        }

    def _reservation_state_label(self, state):
        return {
            "draft": _("Pendiente"),
            "confirmed": _("Confirmada"),
            "seated": _("En curso"),
            "done": _("Finalizada"),
            "cancelled": _("Cancelada"),
        }.get(state, state)

    def _reservation_state_class(self, state):
        return {
            "draft": "secondary",
            "confirmed": "info",
            "seated": "warning",
            "done": "success",
            "cancelled": "dark",
        }.get(state, "light")

    def _reservation_can_be_cancelled(self, reservation):
        return reservation.state in ("draft", "confirmed")

    @http.route(
        ["/my/reservations", "/my/reservations/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_reservations(self, page=1, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id.commercial_partner_id
        Reservation = request.env["restaurant.table.reservation"].sudo()
        domain = self._get_reservation_domain(partner)

        searchbar_sortings = self._reservation_searchbar_sortings()
        if not sortby:
            sortby = "date_desc"
        order_by = searchbar_sortings[sortby]["order"]

        searchbar_filters = self._reservation_searchbar_filters()
        if not filterby:
            filterby = "active"
        domain += searchbar_filters[filterby]["domain"]

        pager = portal_pager(
            url="/my/reservations",
            url_args={"sortby": sortby, "filterby": filterby},
            total=Reservation.search_count(domain),
            page=page,
            step=15,
        )

        reservations = Reservation.search(domain, order=order_by, limit=15, offset=pager["offset"])
        request.session["my_reservations_history"] = reservations.ids[:100]

        rows = [
            {
                "record": reservation,
                "state_label": self._reservation_state_label(reservation.state),
                "state_class": self._reservation_state_class(reservation.state),
                "can_cancel": self._reservation_can_be_cancelled(reservation),
                "detail_url": f"/my/reservations/{reservation.id}",
            }
            for reservation in reservations
        ]

        values.update(
            {
                "reservation_rows": rows,
                "page_name": "reservation",
                "pager": pager,
                "default_url": "/my/reservations",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby,
                "success_message": _("Reserva creada correctamente.") if kw.get("success") else "",
                "cancel_message": _("Reserva cancelada.") if kw.get("cancelled") else "",
                "rescheduled_message": _("Reserva reprogramada correctamente.") if kw.get("rescheduled") else "",
                "cancel_error": kw.get("cancel_error"),
            }
        )
        return request.render("restaurant_table_reservations.portal_my_reservations", values)

    @http.route(["/my/reservations/<int:reservation_id>"], type="http", auth="user", website=True)
    def portal_my_reservation_detail(self, reservation_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        reservation = request.env["restaurant.table.reservation"].sudo().search(
            self._get_reservation_domain(partner) + [("id", "=", reservation_id)],
            limit=1,
        )
        if not reservation:
            return request.redirect("/my/reservations")

        values = self._prepare_portal_layout_values()
        values.update(
            {
                "reservation": reservation,
                "state_label": self._reservation_state_label(reservation.state),
                "state_class": self._reservation_state_class(reservation.state),
                "can_cancel": self._reservation_can_be_cancelled(reservation),
                "cancel_error": kw.get("cancel_error"),
                "page_name": "reservation",
            }
        )
        values = self._get_page_view_values(
            reservation,
            False,
            values,
            "my_reservations_history",
            False,
            **kw,
        )
        return request.render("restaurant_table_reservations.portal_my_reservation_page", values)

    @http.route(
        ["/my/reservations/<int:reservation_id>/cancel"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_my_reservation_cancel(self, reservation_id, **post):
        partner = request.env.user.partner_id.commercial_partner_id
        reservation = request.env["restaurant.table.reservation"].sudo().search(
            self._get_reservation_domain(partner) + [("id", "=", reservation_id)],
            limit=1,
        )
        if not reservation:
            return request.redirect("/my/reservations")
        if not self._reservation_can_be_cancelled(reservation):
            return request.redirect(f"/my/reservations/{reservation.id}?cancel_error=state")
        try:
            reservation.action_cancel()
        except UserError:
            return request.redirect(f"/my/reservations/{reservation.id}?cancel_error=blocked")
        return request.redirect("/my/reservations?cancelled=1")
