from odoo import fields, models


class RestaurantKitchenOrderLine(models.Model):
    _name = "restaurant.kitchen.order.line"
    _description = "Linea de Orden de Cocina"

    kitchen_order_id = fields.Many2one(
        "restaurant.kitchen.order",
        string="Orden de Cocina",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
    )
    quantity = fields.Float(
        string="Cantidad",
        default=1.0,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de Medida",
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )
    line_note = fields.Char(
        string="Nota de linea",
    )
    source_pos_line_uuid = fields.Char(
        string="UUID linea POS",
        index=True,
        help="Identificador unico de la linea POS de origen, para evitar duplicados.",
    )
    state = fields.Selection(
        [
            ("new", "Nueva"),
            ("preparing", "En Preparacion"),
            ("ready", "Lista"),
            ("served", "Servida"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="new",
    )
