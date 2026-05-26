from datetime import timedelta
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


POS_RESERVATION_BUS_CHANNEL = "restaurant_table_reservations.snapshot"
POS_RESERVATION_BUS_NOTIFICATION = "restaurant_table_reservations.snapshot_changed"


class RestaurantTableReservation(models.Model):
    _name = "restaurant.table.reservation"
    _description = "Reserva de mesa"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"

    RESERVATION_MINUTES = 60
    BUFFER_MINUTES = 15

    name = fields.Char(string="Referencia", required=True, default=lambda self: _("Nueva reserva"), copy=False)
    customer_name = fields.Char(string="Cliente", required=True, tracking=True)
    customer_phone = fields.Char(string="Telefono", tracking=True)
    party_size = fields.Integer(string="Personas", required=True, default=2, tracking=True)
    zone = fields.Selection(
        [
            ("main", "Interior"),
            ("patio", "Patio"),
        ],
        string="Zona preferida",
        required=True,
        default="main",
        tracking=True,
    )
    table_id = fields.Many2one("restaurant.table", string="Mesa", required=True, tracking=True)
    start_datetime = fields.Datetime(string="Inicio", required=True, tracking=True)
    end_datetime = fields.Datetime(string="Fin", required=True, tracking=True)
    notes = fields.Text(string="Notas")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmada"),
            ("seated", "Sentados"),
            ("done", "Finalizada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    arrangement_type = fields.Selection(
        [
            ('none', 'Ninguno'),
            ('birthday', 'Decoración Cumpleaños +$10.00'),
            ('anniversary', 'Decoración Aniversario +$15.00'),
            ('romantic', 'Cita Romántica +$20.00'),
            ('general', 'Arreglo Especial +$5.00'),
        ],
        string="Arreglo Especial para la mesa",
        default='none',
        tracking=True,
    )

    arrangement_charged = fields.Boolean(
        string="Arreglo Cobrado",
        default=False,
        help="Indica si el cargo por arreglo ya fue añadido a la orden POS para evitar dobles cargos.",
    )

    def _get_arrangement_cost(self):
        """Return the numeric cost for the selected arrangement type."""
        cost_map = {
            "none": 0.0,
            "birthday": 10.0,
            "anniversary": 15.0,
            "romantic": 20.0,
            "general": 5.0,
        }
        return cost_map.get(self.arrangement_type or "none", 0.0)

    # ------------------------------------------------------------------
    # Onchange helpers
    # ------------------------------------------------------------------

    @api.onchange("start_datetime")
    def _onchange_start_datetime(self):
        for reservation in self:
            if reservation.start_datetime:
                reservation.end_datetime = reservation._get_end_datetime(reservation.start_datetime)

    @api.onchange("zone", "party_size")
    def _onchange_zone_party_size(self):
        for reservation in self:
            if reservation.table_id and (
                reservation.table_id.zone != reservation.zone
                or reservation.table_id.seats < reservation.party_size
            ):
                reservation.table_id = False

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    @api.model
    def _get_end_datetime(self, start_datetime):
        return start_datetime + timedelta(minutes=self.RESERVATION_MINUTES + self.BUFFER_MINUTES)

    @api.model
    def _get_arrangement_label(self, arrangement_type):
        labels = OrderedDict([
            ('none', 'Ninguno'),
            ('birthday', 'Decoración Cumpleaños +$10.00'),
            ('anniversary', 'Decoración Aniversario +$15.00'),
            ('romantic', 'Cita Romántica +$20.00'),
            ('general', 'Arreglo Especial +$5.00'),
        ])
        return labels.get(arrangement_type or 'none', labels['none'])

    @api.model
    def _get_arrangement_cost_label(self, arrangement_type):
        cost_labels = {
            'none': '',
            'birthday': '+$10.00',
            'anniversary': '+$15.00',
            'romantic': '+$20.00',
            'general': '+$5.00',
        }
        return cost_labels.get(arrangement_type or 'none', '')

    @api.model
    def _validate_requested_start_datetime(self, start_datetime):
        current_utc = fields.Datetime.now()
        if start_datetime < current_utc:
            raise ValidationError(_("No puedes reservar en un horario anterior al momento actual."))

    @api.model
    def _get_time_options(self, date_value, start_hour=8, end_hour=22, step_minutes=15):
        """Return allowed time options for a given date, clipping past times on the current day."""
        if not date_value:
            return []

        today_local = fields.Date.context_today(self)
        selected_date = fields.Date.from_string(date_value)
        start_total_minutes = start_hour * 60

        if selected_date == today_local:
            now_local = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            current_minutes = now_local.hour * 60 + now_local.minute
            start_total_minutes = max(start_total_minutes, ((current_minutes + step_minutes - 1) // step_minutes) * step_minutes)

        options = []
        for total_minutes in range(start_total_minutes, (end_hour * 60) + 1, step_minutes):
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if hours < start_hour or hours > end_hour:
                continue
            options.append(f"{hours:02d}:{minutes:02d}")
        return options

    @api.model
    def _get_floor_ids_for_zone(self, zone):
        """Return floor IDs that match a given zone code."""
        floors = self.env["restaurant.floor"].sudo().search([])
        zone_keyword = {"main": "interior", "patio": "patio"}.get(zone, "")
        return [
            f.id for f in floors
            if zone_keyword and zone_keyword in (f.name or "").strip().lower()
        ]

    @api.model
    def _get_available_tables(self, start_datetime, party_size, zone=None, exclude_reservation_id=None):
        """Return available tables as a list of dicts with uniform keys."""
        end_datetime = self._get_end_datetime(start_datetime)

        sql = [
            "SELECT t.id,",
            "  COALESCE(t.table_number, 0) AS table_number,",
            "  COALESCE(t.seats, 0) AS seats,",
            "  COALESCE(f.name, '') AS floor_name",
            "FROM restaurant_table t",
            "LEFT JOIN restaurant_floor f ON f.id = t.floor_id",
            "WHERE t.active IS TRUE",
        ]
        params = []

        if zone:
            floor_ids = self._get_floor_ids_for_zone(zone)
            if floor_ids:
                sql.append("AND t.floor_id IN %s")
                params.append(tuple(floor_ids))
            else:
                # No valid floors for this zone → return empty
                return []

        sql.append("ORDER BY t.table_number ASC")
        self.env.cr.execute(" ".join(sql), params)
        tables = self.env.cr.dictfetchall()

        available_tables = []
        for table in tables:
            if table["seats"] < party_size:
                continue

            overlap_domain = [
                ("id", "!=", exclude_reservation_id or 0),
                ("table_id", "=", table["id"]),
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ]
            if not self.search_count(overlap_domain):
                # Determine zone from floor name
                fname = (table["floor_name"] or "").strip().lower()
                if "interior" in fname:
                    table_zone = "main"
                elif "patio" in fname:
                    table_zone = "patio"
                else:
                    table_zone = ""

                available_tables.append({
                    "id": table["id"],
                    "name": str(table["table_number"]),
                    "capacity": table["seats"],
                    "zone": table_zone,
                    "notes": "",
                })

        return available_tables

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model
    def _sync_reservation_window(self, vals):
        if vals.get("start_datetime"):
            start_datetime = fields.Datetime.to_datetime(vals["start_datetime"])
            vals["end_datetime"] = fields.Datetime.to_string(self._get_end_datetime(start_datetime))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        synced_vals_list = [self._sync_reservation_window(dict(vals)) for vals in vals_list]
        for vals in synced_vals_list:
            if vals.get("start_datetime"):
                self._validate_requested_start_datetime(fields.Datetime.to_datetime(vals["start_datetime"]))
            if vals.get("arrangement_type"):
                vals["arrangement_type"] = vals["arrangement_type"] or "none"
        return super().create(synced_vals_list)

    def write(self, vals):
        if vals.get("start_datetime"):
            vals = dict(vals)
            start_datetime = fields.Datetime.to_datetime(vals["start_datetime"])
            self._validate_requested_start_datetime(start_datetime)
            vals["end_datetime"] = fields.Datetime.to_string(self._get_end_datetime(start_datetime))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("party_size", "start_datetime", "end_datetime", "table_id", "state")
    def _check_reservation_rules(self):
        for reservation in self:
            if reservation.party_size <= 0:
                raise ValidationError(_("La cantidad de personas debe ser mayor a cero."))
            if reservation.table_id and reservation.party_size > reservation.table_id.seats:
                raise ValidationError(_("La reserva supera la capacidad de la mesa seleccionada."))
            if reservation.table_id and reservation.table_id.zone != reservation.zone:
                raise ValidationError(_("La mesa seleccionada no coincide con la zona preferida."))
            if reservation.start_datetime and reservation.end_datetime:
                if reservation.end_datetime <= reservation.start_datetime:
                    raise ValidationError(_("La hora de fin debe ser posterior a la hora de inicio."))
            if not reservation.table_id or reservation.state in ("cancelled", "done"):
                continue
            domain = [
                ("id", "!=", reservation.id),
                ("table_id", "=", reservation.table_id.id),
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<", reservation.end_datetime),
                ("end_datetime", ">", reservation.start_datetime),
            ]
            if reservation.start_datetime and reservation.end_datetime and self.search_count(domain):
                raise ValidationError(_("Ya existe una reserva activa para esa mesa en el horario indicado."))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_confirm(self):
        self.write({"state": "confirmed"})
        self._notify_pos_reservation_change()

    def action_seated(self):
        self.write({"state": "seated"})
        self._notify_pos_reservation_change()

    def action_done(self):
        self.write({"state": "done"})
        self._notify_pos_reservation_change()

    def action_cancel(self):
        active = self.filtered(lambda reservation: reservation.state in ("seated", "done"))
        if active:
            raise UserError(_("No puede cancelar una reserva sentada o finalizada."))
        self.write({"state": "cancelled"})
        self._notify_pos_reservation_change()

    def _notify_pos_reservation_change(self, table_ids=None):
        self.env["bus.bus"]._sendone(
            POS_RESERVATION_BUS_CHANNEL,
            POS_RESERVATION_BUS_NOTIFICATION,
            {"table_ids": table_ids or self.mapped("table_id").ids},
        )
