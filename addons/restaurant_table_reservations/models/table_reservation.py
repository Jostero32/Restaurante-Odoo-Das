from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
            ("private", "Privado"),
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

    @api.onchange("start_datetime")
    def _onchange_start_datetime(self):
        for reservation in self:
            if reservation.start_datetime:
                reservation.end_datetime = reservation._get_end_datetime(reservation.start_datetime)

    @api.onchange("zone", "party_size")
    def _onchange_zone_party_size(self):
        for reservation in self:
            if reservation.table_id and (
                reservation.table_id.zone != reservation.zone or reservation.table_id.capacity < reservation.party_size
            ):
                reservation.table_id = False

    @api.model
    def _get_end_datetime(self, start_datetime):
        return start_datetime + timedelta(minutes=self.RESERVATION_MINUTES + self.BUFFER_MINUTES)

    @api.model
    def _get_available_tables(self, start_datetime, party_size, zone=None, exclude_reservation_id=None):
        end_datetime = self._get_end_datetime(start_datetime)
        sql = [
            "SELECT id, COALESCE(name, 'Mesa ' || id::text) AS name, COALESCE(capacity, 0) AS capacity, COALESCE(zone, '') AS zone, COALESCE(notes, '') AS notes",
            "FROM restaurant_table",
            "WHERE active IS TRUE",
        ]
        params = []
        if zone:
            sql.append("AND zone = %s")
            params.append(zone)

        sql.append("ORDER BY id ASC")
        self.env.cr.execute(" ".join(sql), params)
        tables = self.env.cr.dictfetchall()
        available_tables = []

        for table in tables:
            if table["capacity"] < party_size:
                continue
            overlap_domain = [
                ("id", "!=", exclude_reservation_id or 0),
                ("table_id", "=", table["id"]),
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ]
            if not self.search_count(overlap_domain):
                available_tables.append(table)

        return available_tables

    @api.model
    def _sync_reservation_window(self, vals):
        if vals.get("start_datetime"):
            start_datetime = fields.Datetime.to_datetime(vals["start_datetime"])
            vals["end_datetime"] = fields.Datetime.to_string(self._get_end_datetime(start_datetime))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        synced_vals_list = [self._sync_reservation_window(dict(vals)) for vals in vals_list]
        return super().create(synced_vals_list)

    def write(self, vals):
        if vals.get("start_datetime"):
            vals = dict(vals)
            start_datetime = fields.Datetime.to_datetime(vals["start_datetime"])
            vals["end_datetime"] = fields.Datetime.to_string(self._get_end_datetime(start_datetime))
        return super().write(vals)

    @api.constrains("party_size", "start_datetime", "end_datetime", "table_id", "state")
    def _check_reservation_rules(self):
        for reservation in self:
            if reservation.party_size <= 0:
                raise ValidationError(_("La cantidad de personas debe ser mayor a cero."))
            if reservation.table_id and reservation.party_size > reservation.table_id.capacity:
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

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_seated(self):
        self.write({"state": "seated"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        active = self.filtered(lambda reservation: reservation.state in ("seated", "done"))
        if active:
            raise UserError(_("No puede cancelar una reserva sentada o finalizada."))
        self.write({"state": "cancelled"})
