from datetime import datetime

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class RestaurantDeliveryWebsiteSale(WebsiteSale):
    def _get_mandatory_billing_address_fields(self, country_sudo):
        mandatory_fields = super()._get_mandatory_billing_address_fields(country_sudo)
        mandatory_fields.discard("vat")
        mandatory_fields.discard("l10n_latam_identification_type_id")
        return mandatory_fields

    def _get_active_delivery_schedule(self):
        company = request.website.sudo().company_id or request.env.company
        return request.env["restaurant.delivery.schedule"].sudo()._get_or_create_for_company(company)

    @http.route(
        ["/shop/delivery_schedule/window"],
        type="json",
        auth="public",
        website=True,
    )
    def shop_delivery_schedule_window(self):
        schedule = self._get_active_delivery_schedule()
        now = fields.Datetime.now()
        window = schedule.get_available_slots_window(reference_dt=now)
        is_open_now = schedule.is_open_at(now)
        local_now = schedule._to_company_local(now)
        days = []
        for entry in window:
            day_date = entry["date"]
            slots = entry["slots"]
            days.append(
                {
                    "date": day_date.isoformat(),
                    "label": self._format_day_label(day_date, local_now.date()),
                    "slots": [
                        {
                            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                            "label": schedule._to_company_local(dt).strftime("%H:%M"),
                        }
                        for dt in slots
                    ],
                }
            )
        return {
            "is_open_now": is_open_now,
            "slot_minutes": schedule.slot_minutes,
            "min_lead_time_minutes": schedule.min_lead_time_minutes,
            "days": days,
            "current_selection": self._read_current_schedule_selection(),
        }

    @http.route(
        ["/shop/delivery_schedule/set"],
        type="json",
        auth="public",
        website=True,
    )
    def shop_delivery_schedule_set(self, is_scheduled=False, scheduled_for=None):
        order = request.website.sale_get_order()
        if not order:
            return {"error": "no_order"}
        if not is_scheduled:
            order.sudo().with_context(skip_delivery_sync=False).write(
                {"delivery_is_scheduled": False, "delivery_scheduled_for": False}
            )
            return {"is_scheduled": False, "scheduled_for": None}
        if not scheduled_for:
            return {"error": "missing_slot"}
        try:
            slot_dt = datetime.strptime(scheduled_for, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {"error": "invalid_slot_format"}
        schedule = self._get_active_delivery_schedule()
        if not schedule.is_open_at(slot_dt):
            return {"error": "slot_outside_hours"}
        order.sudo().write(
            {"delivery_is_scheduled": True, "delivery_scheduled_for": slot_dt}
        )
        return {
            "is_scheduled": True,
            "scheduled_for": slot_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "scheduled_label": schedule._to_company_local(slot_dt).strftime("%d/%m %H:%M"),
        }

    def _format_day_label(self, day_date, today):
        delta_days = (day_date - today).days
        if delta_days == 0:
            return "Hoy"
        if delta_days == 1:
            return "Manana"
        day_names = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        return f"{day_names[day_date.weekday()]} {day_date.day:02d}/{day_date.month:02d}"

    def _read_current_schedule_selection(self):
        order = request.website.sale_get_order()
        if not order:
            return {"is_scheduled": False, "scheduled_for": None}
        if not order.delivery_is_scheduled or not order.delivery_scheduled_for:
            return {"is_scheduled": False, "scheduled_for": None}
        schedule = self._get_active_delivery_schedule()
        return {
            "is_scheduled": True,
            "scheduled_for": order.delivery_scheduled_for.strftime("%Y-%m-%d %H:%M:%S"),
            "scheduled_label": schedule._to_company_local(order.delivery_scheduled_for).strftime("%d/%m %H:%M"),
        }
