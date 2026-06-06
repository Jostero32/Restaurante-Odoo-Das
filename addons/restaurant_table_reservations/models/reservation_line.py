from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RestaurantTableReservationLine(models.Model):
    _name = "restaurant.table.reservation.line"
    _description = "Linea de pre-orden de reserva"
    _order = "reservation_id, sequence, id"

    reservation_id = fields.Many2one(
        "restaurant.table.reservation",
        string="Reserva",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('product_tmpl_id.available_for_reservation_preorder', '=', True)]",
    )
    name = fields.Char(string="Descripcion")
    qty = fields.Float(string="Cantidad", required=True, default=1.0)
    price_unit = fields.Float(string="Precio unitario", required=True, default=0.0)
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_price_subtotal",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="reservation_id.currency_id",
        store=True,
        readonly=True,
    )
    notes = fields.Char(string="Notas")

    @api.depends("qty", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = (line.qty or 0.0) * (line.price_unit or 0.0)

    @api.constrains("qty")
    def _check_qty(self):
        for line in self:
            if line.qty <= 0:
                raise ValidationError(_("La cantidad del producto debe ser mayor a cero."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.name = line.product_id.display_name
                if not line.price_unit:
                    line.price_unit = line.product_id.lst_price
