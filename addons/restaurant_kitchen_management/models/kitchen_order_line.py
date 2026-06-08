from odoo import fields, models


class RestaurantKitchenOrderLine(models.Model):
    _name = "restaurant.kitchen.order.line"
    _description = "Linea de Orden de Cocina"
    _order = "sequence, id"

    # Req 1: orden de preparacion de las lineas dentro de la orden
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
        help="Orden en que se preparan las lineas dentro de la orden de cocina.",
    )
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
    # Req 5: nivel de coccion solicitado (ej: termino medio, bien cocido)
    cooking_preference = fields.Char(
        string="Coccion",
        help="Nivel de coccion solicitado por el cliente.",
    )
    # Req 4: cambios de ingredientes (agregar / quitar)
    ingredient_changes = fields.Char(
        string="Cambios de ingredientes",
        help="Ingredientes a agregar o quitar para esta linea (ej: sin cebolla, extra queso).",
    )
    # Req 1: pasos de preparacion del plato (referencia para el cocinero)
    prep_steps = fields.Text(
        string="Pasos de preparacion",
        related="product_id.product_tmpl_id.kitchen_prep_steps",
        readonly=True,
    )
    # Req 3: alergenos del plato (referencia para el cocinero)
    allergens = fields.Char(
        string="Alergenos del plato",
        related="product_id.product_tmpl_id.kitchen_allergens",
        readonly=True,
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
