from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RestaurantTable(models.Model):
    _name = "restaurant.table"
    _description = "Mesa del restaurante"
    _order = "name"

    name = fields.Char(string="Mesa", required=True)
    capacity = fields.Integer(string="Capacidad", required=True, default=4)
    zone = fields.Selection(
        [
            ("main", "Salon principal"),
            ("terrace", "Terraza"),
            ("private", "Privado"),
        ],
        string="Zona",
        default="main",
        required=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Notas")

    @api.constrains("capacity")
    def _check_capacity(self):
        for table in self:
            if table.capacity <= 0:
                raise ValidationError(_("La capacidad de la mesa debe ser mayor a cero."))
