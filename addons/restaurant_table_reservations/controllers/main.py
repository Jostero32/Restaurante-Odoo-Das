import json
from datetime import datetime
from urllib.parse import quote_plus

from odoo import fields, http, _
from odoo.exceptions import ValidationError
from odoo.http import request


class RestaurantTableReservationController(http.Controller):
    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _get_local_tz(self):
        # 1. Check Odoo context
        tz = request.context.get("tz")
        if tz:
            return tz
        # 2. Check current user tz
        if request.env.user and request.env.user.tz:
            return request.env.user.tz
        # 3. Check if any admin or partner has tz configured
        user_with_tz = request.env["res.users"].sudo().search([("tz", "!=", False)], limit=1)
        if user_with_tz:
            return user_with_tz.tz
        # 4. Fallback
        return "America/Bogota"

    def _local_to_utc(self, naive_dt):
        if not naive_dt:
            return None
        import pytz
        tz_name = self._get_local_tz()
        local_tz = pytz.timezone(tz_name)
        local_dt = local_tz.localize(naive_dt, is_dst=None)
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def _parse_start_datetime(self, date_value, time_value):
        if not date_value or not time_value:
            return None
        naive_dt = datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
        return self._local_to_utc(naive_dt)

    def _build_context(self, **kwargs):
        reservation_model = request.env["restaurant.table.reservation"].sudo()
        zone = kwargs.get("zone") or "main"
        party_size = self._safe_int(kwargs.get("party_size"), 2)
        start_datetime = self._parse_start_datetime(kwargs.get("date"), kwargs.get("time"))

        available_tables = []
        reservation_window_end = False
        if start_datetime:
            end_datetime = reservation_model._get_end_datetime(start_datetime)
            reservation_window_end = fields.Datetime.to_string(end_datetime) + "Z"
            available_tables = reservation_model._get_available_tables(start_datetime, party_size, zone=zone)

        zone_options = [
            ("main", "Interior"),
            ("patio", "Patio"),
        ]

        return {
            "zone_options": zone_options,
            "selected_zone": zone,
            "selected_party_size": party_size,
            "selected_date": kwargs.get("date") or "",
            "selected_time": kwargs.get("time") or "",
            "available_tables": available_tables,
            "reservation_window_end": reservation_window_end,
            "reservation_duration_minutes": reservation_model.RESERVATION_MINUTES,
            "reservation_buffer_minutes": reservation_model.BUFFER_MINUTES,
        }

    @http.route(["/reservas", "/reservas/mesa"], type="http", auth="public", website=True, sitemap=True)
    def reservation_page(self, **kwargs):
        context = self._build_context(**kwargs)
        context.update(
            {
                "success_message": request.params.get("success") and _("Su reserva fue enviada correctamente."),
                "error_message": request.params.get("error"),
                "selected_table_id": self._safe_int(kwargs.get("table_id"), 0),
                "customer_name": kwargs.get("customer_name") or "",
                "customer_phone": kwargs.get("customer_phone") or "",
                "notes": kwargs.get("notes") or "",
            }
        )
        return request.render("restaurant_table_reservations.reservation_page", context)

    @http.route("/reservas/availability", type="http", auth="public", website=True, methods=["GET"], csrf=False)
    def reservation_availability(self, **kwargs):
        context = self._build_context(**kwargs)
        payload = {
            "available_tables": [
                {
                    "id": table["id"],
                    "name": table["name"],
                    "capacity": table["capacity"],
                    "zone": table["zone"],
                    "zone_label": {
                        "main": "Interior",
                        "patio": "Patio",
                    }.get(table["zone"], table["zone"]),
                    "notes": table.get("notes", ""),
                }
                for table in context["available_tables"]
            ],
            "reservation_window_end": context["reservation_window_end"],
            "reservation_duration_minutes": context["reservation_duration_minutes"],
            "reservation_buffer_minutes": context["reservation_buffer_minutes"],
            "selected_zone": context["selected_zone"],
            "selected_party_size": context["selected_party_size"],
        }
        return request.make_response(json.dumps(payload), headers=[("Content-Type", "application/json")])

    @http.route("/reservas/create", type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def reservation_create(self, **post):
        start_datetime = self._parse_start_datetime(post.get("date"), post.get("time"))
        if not start_datetime:
            return request.redirect("/reservas?error=Debes seleccionar una fecha y una hora.")

        try:
            table_id = self._safe_int(post.get("table_id"), 0)
            if not table_id:
                raise ValidationError(_("Debes elegir una mesa disponible."))

            reservation_model = request.env["restaurant.table.reservation"].sudo()
            reservation_model.create(
                {
                    "customer_name": post.get("customer_name") or "",
                    "customer_phone": post.get("customer_phone") or "",
                    "party_size": int(post.get("party_size") or 2),
                    "zone": post.get("zone") or "main",
                    "table_id": table_id,
                    "start_datetime": fields.Datetime.to_string(start_datetime),
                    "notes": post.get("notes") or "",
                }
            )
        except (ValidationError, ValueError) as error:
            return request.redirect(f"/reservas?error={quote_plus(str(error))}")

        return request.redirect("/reservas?success=1")