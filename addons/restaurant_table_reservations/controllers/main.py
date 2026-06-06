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
        tz = request.context.get("tz")
        if tz:
            return tz
        if request.env.user and request.env.user.tz:
            return request.env.user.tz
        user_with_tz = request.env["res.users"].sudo().search([("tz", "!=", False)], limit=1)
        if user_with_tz:
            return user_with_tz.tz
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

    def _parse_pre_order_payload(self, payload):
        if not payload:
            return []
        try:
            raw_items = json.loads(payload)
        except (TypeError, ValueError):
            raise ValidationError(_("No se pudo procesar la pre-orden enviada."))
        if not isinstance(raw_items, list):
            raise ValidationError(_("Formato invalido para la pre-orden."))
        parsed = []
        Product = request.env["product.product"].sudo()
        for item in raw_items:
            product_id = self._safe_int(item.get("product_id"), 0)
            try:
                qty = float(item.get("qty") or 0.0)
            except (TypeError, ValueError):
                qty = 0.0
            notes = (item.get("notes") or "").strip()
            if not product_id or qty <= 0:
                continue
            product = Product.search(
                [
                    ("id", "=", product_id),
                    ("active", "=", True),
                    ("sale_ok", "=", True),
                    ("product_tmpl_id.available_for_reservation_preorder", "=", True),
                ],
                limit=1,
            )
            if not product:
                raise ValidationError(_("Uno de los productos del pre-pedido ya no esta disponible."))
            parsed.append(
                {
                    "product_id": product.id,
                    "qty": qty,
                    "notes": notes[:500],
                    "price_unit": product.lst_price,
                    "name": product.display_name,
                }
            )
        return parsed

    def _resolve_reschedule_source(self, reschedule_from):
        if not reschedule_from:
            return None
        try:
            source_id = int(reschedule_from)
        except (TypeError, ValueError):
            return None
        partner = request.env.user.partner_id.commercial_partner_id
        source = request.env["restaurant.table.reservation"].sudo().search(
            [
                ("id", "=", source_id),
                ("partner_id", "child_of", [partner.id]),
                ("state", "in", ("draft", "confirmed")),
            ],
            limit=1,
        )
        return source or None

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

        schedule_status = reservation_model._get_schedule_status_for_date(kwargs.get("date"))
        schedule = reservation_model._get_business_schedule()

        return {
            "zone_options": zone_options,
            "selected_zone": zone,
            "selected_party_size": party_size,
            "selected_date": kwargs.get("date") or "",
            "selected_time": kwargs.get("time") or "",
            "selected_arrangement_product_id": self._safe_int(kwargs.get("arrangement_product_id"), 0),
            "arrangement_options": reservation_model._get_arrangement_products(),
            "available_time_options": reservation_model._get_time_options(kwargs.get("date")),
            "available_tables": available_tables,
            "reservation_window_end": reservation_window_end,
            "reservation_duration_minutes": reservation_model.RESERVATION_MINUTES,
            "reservation_buffer_minutes": reservation_model.BUFFER_MINUTES,
            "schedule_is_open": schedule_status["is_open"],
            "schedule_message": schedule_status["message"],
            "schedule_max_days": schedule.max_schedule_days or 7,
            "schedule_min_lead_minutes": schedule.min_lead_time_minutes or 0,
        }

    @http.route(["/reservas", "/reservas/mesa"], type="http", auth="user", website=True, sitemap=True)
    def reservation_page(self, **kwargs):
        source = self._resolve_reschedule_source(kwargs.get("reschedule_from"))
        if source:
            local_start = fields.Datetime.context_timestamp(source, source.start_datetime)
            kwargs.setdefault("date", local_start.date().isoformat())
            kwargs.setdefault("time", local_start.strftime("%H:%M"))
            kwargs.setdefault("zone", source.zone)
            kwargs.setdefault("party_size", str(source.party_size))
            kwargs.setdefault("arrangement_product_id", str(source.arrangement_product_id.id) if source.arrangement_product_id else "0")
            kwargs.setdefault("notes", source.notes or "")
        context = self._build_context(**kwargs)
        context.update(
            {
                "success_message": request.params.get("success") and _("Su reserva fue enviada correctamente."),
                "error_message": request.params.get("error"),
                "pre_order_products": request.env["restaurant.table.reservation"].sudo()._get_pre_order_products(),
                "currency_symbol": request.env.company.currency_id.symbol or "$",
                "selected_table_id": self._safe_int(kwargs.get("table_id"), 0),
                "customer_name": kwargs.get("customer_name") or "",
                "customer_phone": kwargs.get("customer_phone") or "",
                "notes": kwargs.get("notes") or "",
                "reschedule_from": source.id if source else False,
                "reschedule_source_name": source.name if source else "",
            }
        )
        return request.render("restaurant_table_reservations.reservation_page", context)

    @http.route("/reservas/availability", type="http", auth="user", website=True, methods=["GET"], csrf=False)
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
            "available_time_options": context["available_time_options"],
            "selected_zone": context["selected_zone"],
            "selected_party_size": context["selected_party_size"],
            "selected_arrangement_type": context.get("selected_arrangement_type", "none"),
            "schedule_is_open": context["schedule_is_open"],
            "schedule_message": context["schedule_message"],
        }
        return request.make_response(json.dumps(payload), headers=[("Content-Type", "application/json")])

    @http.route("/reservas/create", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def reservation_create(self, **post):
        start_datetime = self._parse_start_datetime(post.get("date"), post.get("time"))
        if not start_datetime:
            return request.redirect("/reservas?error=Debes seleccionar una fecha y una hora.")

        source = self._resolve_reschedule_source(post.get("reschedule_from"))

        try:
            table_id = self._safe_int(post.get("table_id"), 0)
            if not table_id:
                raise ValidationError(_("Debes elegir una mesa disponible."))
            pre_order_items = self._parse_pre_order_payload(post.get("pre_order_payload"))

            partner = request.env.user.partner_id.commercial_partner_id
            reservation_model = request.env["restaurant.table.reservation"].sudo()

            # Adquirir un lock exclusivo sobre la fila de la mesa ANTES de verificar
            # disponibilidad. Esto serializa reservas concurrentes para la misma mesa
            # y elimina la ventana de doble-reserva entre el chequeo y el INSERT.
            try:
                request.env.cr.execute(
                    "SELECT id FROM restaurant_table WHERE id = %s FOR UPDATE",
                    (table_id,),
                )
                if not request.env.cr.fetchone():
                    raise ValidationError(_("La mesa seleccionada no existe."))
            except ValidationError:
                raise
            except Exception:
                raise ValidationError(
                    _("No fue posible verificar la disponibilidad de la mesa. Intenta de nuevo.")
                )

            # Re-validar disponibilidad en el servidor, ya con el lock, por si
            # otra solicitud concurrente acabo de tomar la mesa entre el form y el POST.
            end_dt_check = reservation_model._get_end_datetime(start_datetime)
            conflicto = reservation_model.search_count([
                ("table_id", "=", table_id),
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<", fields.Datetime.to_string(end_dt_check)),
                ("end_datetime", ">", fields.Datetime.to_string(start_datetime)),
            ])
            if conflicto:
                raise ValidationError(
                    _("La mesa fue reservada por otro usuario en este momento. Por favor elige otra mesa u horario.")
                )

            arrangement_product_id = self._safe_int(post.get("arrangement_product_id"), 0)
            reservation_vals = {
                "partner_id": partner.id,
                "customer_name": post.get("customer_name") or partner.name or "",
                "customer_phone": post.get("customer_phone") or partner.phone or partner.mobile or "",
                "party_size": int(post.get("party_size") or 2),
                "zone": post.get("zone") or "main",
                "table_id": table_id,
                "start_datetime": fields.Datetime.to_string(start_datetime),
                "notes": post.get("notes") or "",
                "arrangement_product_id": arrangement_product_id or False,
            }
            if pre_order_items:
                reservation_vals["pre_order_line_ids"] = [
                    (
                        0,
                        0,
                        {
                            "product_id": item["product_id"],
                            "name": item["name"],
                            "qty": item["qty"],
                            "notes": item["notes"],
                            "price_unit": item["price_unit"],
                        },
                    )
                    for item in pre_order_items
                ]
            reservation = reservation_model.create(reservation_vals)
            reservation.action_confirm()
            if source:
                source.action_cancel()
        except (ValidationError, ValueError) as error:
            return request.redirect(f"/reservas?error={quote_plus(str(error))}")

        suffix = "rescheduled=1" if source else "success=1"
        return request.redirect(f"/my/reservations?{suffix}")
