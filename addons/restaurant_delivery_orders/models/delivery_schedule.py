from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


DAY_OF_WEEK_SELECTION = [
    ("0", "Lunes"),
    ("1", "Martes"),
    ("2", "Miercoles"),
    ("3", "Jueves"),
    ("4", "Viernes"),
    ("5", "Sabado"),
    ("6", "Domingo"),
]


def _float_to_time(value):
    if value is None:
        return None
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes >= 60:
        hours += 1
        minutes -= 60
    return time(hour=max(0, min(23, hours)), minute=max(0, min(59, minutes)))


class RestaurantDeliverySchedule(models.Model):
    _name = "restaurant.delivery.schedule"
    _description = "Horario de delivery"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        "restaurant.delivery.schedule.line",
        "schedule_id",
        string="Franjas semanales",
    )
    exception_ids = fields.One2many(
        "restaurant.delivery.schedule.exception",
        "schedule_id",
        string="Excepciones",
    )
    slot_minutes = fields.Integer(
        string="Granularidad de slots (min)",
        default=30,
        required=True,
        help="Intervalo entre slots ofrecidos al cliente al programar una entrega.",
    )
    min_lead_time_minutes = fields.Integer(
        string="Anticipacion minima (min)",
        default=30,
        required=True,
        help="Minutos minimos entre el momento actual y la entrega programable mas cercana.",
    )
    max_schedule_days = fields.Integer(
        string="Anticipacion maxima (dias)",
        default=7,
        required=True,
        help="Hasta cuantos dias en el futuro puede el cliente programar una entrega.",
    )

    _sql_constraints = [
        (
            "company_unique",
            "unique(company_id)",
            "Solo puede existir un horario de delivery por compania.",
        ),
    ]

    @api.constrains("slot_minutes", "min_lead_time_minutes", "max_schedule_days")
    def _check_positive_values(self):
        for schedule in self:
            if schedule.slot_minutes <= 0:
                raise ValidationError(_("La granularidad de slots debe ser mayor a cero."))
            if 60 % schedule.slot_minutes != 0 and schedule.slot_minutes % 60 != 0:
                raise ValidationError(_("La granularidad debe ser divisor de 60 (ej. 15, 20, 30, 60)."))
            if schedule.min_lead_time_minutes < 0:
                raise ValidationError(_("La anticipacion minima no puede ser negativa."))
            if schedule.max_schedule_days <= 0:
                raise ValidationError(_("La anticipacion maxima debe ser mayor a cero."))

    @api.model
    def _get_or_create_for_company(self, company=None):
        company = company or self.env.company
        schedule = self.search([("company_id", "=", company.id)], limit=1)
        if schedule:
            return schedule
        return self.create({"company_id": company.id})

    def _exception_for_date(self, day_date):
        self.ensure_one()
        return self.exception_ids.filtered(lambda exc: exc.date == day_date)[:1]

    def _ranges_for_date(self, day_date):
        """Return list of (time_from, time_to) tuples active for the given date."""
        self.ensure_one()
        exception = self._exception_for_date(day_date)
        if exception:
            if exception.is_closed:
                return []
            if exception.time_from is not None and exception.time_to is not None and exception.time_to > exception.time_from:
                return [(exception.time_from, exception.time_to)]
            return []
        weekday = str(day_date.weekday())
        lines = self.line_ids.filtered(lambda line: line.day_of_week == weekday)
        ranges = []
        for line in lines:
            if line.time_to > line.time_from:
                ranges.append((line.time_from, line.time_to))
        ranges.sort()
        return ranges

    def is_open_at(self, check_dt):
        """Return True if delivery is operating at the given datetime."""
        self.ensure_one()
        if not check_dt:
            return False
        local_dt = self._to_company_local(check_dt)
        decimal_hour = local_dt.hour + local_dt.minute / 60.0
        for time_from, time_to in self._ranges_for_date(local_dt.date()):
            if time_from <= decimal_hour < time_to:
                return True
        return False

    def get_available_slots(self, day_date, reference_dt=None):
        """Generate scheduling slots (as naive UTC datetimes) for a given date."""
        self.ensure_one()
        ranges = self._ranges_for_date(day_date)
        if not ranges:
            return []
        reference_dt = reference_dt or fields.Datetime.now()
        slot_delta = timedelta(minutes=self.slot_minutes)
        min_dt = reference_dt + timedelta(minutes=self.min_lead_time_minutes)
        results = []
        for time_from, time_to in ranges:
            start_time = _float_to_time(time_from)
            end_time = _float_to_time(time_to)
            local_start = datetime.combine(day_date, start_time)
            local_end = datetime.combine(day_date, end_time)
            current_local = local_start
            while current_local + slot_delta <= local_end:
                utc_dt = self._to_utc(current_local)
                if utc_dt >= min_dt:
                    results.append(utc_dt)
                current_local += slot_delta
        return results

    def get_available_slots_window(self, reference_dt=None):
        """Return list of dicts with date and slots for the whole scheduling window."""
        self.ensure_one()
        reference_dt = reference_dt or fields.Datetime.now()
        local_now = self._to_company_local(reference_dt)
        window = []
        for offset in range(self.max_schedule_days + 1):
            day_date = (local_now + timedelta(days=offset)).date()
            slots = self.get_available_slots(day_date, reference_dt=reference_dt)
            if slots:
                window.append({"date": day_date, "slots": slots})
        return window

    def _to_company_local(self, dt_value):
        """Convert a naive UTC datetime to the company timezone, returning naive local datetime."""
        from pytz import UTC, timezone

        tz_name = self.company_id.partner_id.tz or self.env.user.tz or "UTC"
        tz = timezone(tz_name)
        if dt_value.tzinfo is None:
            dt_value = UTC.localize(dt_value)
        return dt_value.astimezone(tz).replace(tzinfo=None)

    def _to_utc(self, naive_local_dt):
        from pytz import UTC, timezone

        tz_name = self.company_id.partner_id.tz or self.env.user.tz or "UTC"
        tz = timezone(tz_name)
        local_aware = tz.localize(naive_local_dt)
        return local_aware.astimezone(UTC).replace(tzinfo=None)


class RestaurantDeliveryScheduleLine(models.Model):
    _name = "restaurant.delivery.schedule.line"
    _description = "Franja semanal de horario de delivery"
    _order = "day_of_week, time_from"

    schedule_id = fields.Many2one(
        "restaurant.delivery.schedule",
        required=True,
        ondelete="cascade",
    )
    day_of_week = fields.Selection(
        DAY_OF_WEEK_SELECTION,
        string="Dia",
        required=True,
    )
    time_from = fields.Float(string="Desde", required=True, default=11.0)
    time_to = fields.Float(string="Hasta", required=True, default=22.0)

    @api.constrains("time_from", "time_to")
    def _check_time_range(self):
        for line in self:
            if not (0.0 <= line.time_from < 24.0):
                raise ValidationError(_("La hora de inicio debe estar entre 0 y 24."))
            if not (0.0 < line.time_to <= 24.0):
                raise ValidationError(_("La hora de fin debe estar entre 0 y 24."))
            if line.time_to <= line.time_from:
                raise ValidationError(_("La hora de fin debe ser posterior a la hora de inicio."))


class RestaurantDeliveryScheduleException(models.Model):
    _name = "restaurant.delivery.schedule.exception"
    _description = "Excepcion de horario (feriado u horario especial)"
    _order = "date desc, id desc"

    schedule_id = fields.Many2one(
        "restaurant.delivery.schedule",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Motivo", required=True)
    date = fields.Date(string="Fecha", required=True)
    is_closed = fields.Boolean(
        string="Cerrado todo el dia",
        default=True,
        help="Si esta marcado, el restaurante no opera ese dia. Si esta desmarcado, se usa el horario especial.",
    )
    time_from = fields.Float(string="Desde (horario especial)")
    time_to = fields.Float(string="Hasta (horario especial)")

    _sql_constraints = [
        (
            "schedule_date_unique",
            "unique(schedule_id, date)",
            "Ya existe una excepcion para esa fecha en este horario.",
        ),
    ]

    @api.constrains("is_closed", "time_from", "time_to")
    def _check_special_hours(self):
        for exc in self:
            if exc.is_closed:
                continue
            if not (0.0 <= exc.time_from < 24.0):
                raise ValidationError(_("La hora de inicio debe estar entre 0 y 24."))
            if not (0.0 < exc.time_to <= 24.0):
                raise ValidationError(_("La hora de fin debe estar entre 0 y 24."))
            if exc.time_to <= exc.time_from:
                raise ValidationError(_("La hora de fin debe ser posterior a la hora de inicio."))
