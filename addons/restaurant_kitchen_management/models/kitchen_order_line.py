from odoo import _, api, fields, models


class RestaurantKitchenOrderLine(models.Model):
    _name = "restaurant.kitchen.order.line"
    _description = "Línea de Orden de Cocina"
    _order = "sequence, id"

    # ─── Relación con la orden ────────────────────────────────────────────────

    kitchen_order_id = fields.Many2one(
        comodel_name="restaurant.kitchen.order",
        string="Orden de Cocina",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(
        string="Secuencia",
        default=10,
        help="Permite ordenar manualmente las líneas dentro de la orden.",
    )

    # ─── Producto ─────────────────────────────────────────────────────────────

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        required=True,
        domain="[('kitchen_preparable', '=', True)]",
        ondelete="restrict",
    )
    product_name = fields.Char(
        string="Descripción",
        help="Nombre del producto en el momento de crear la línea. "
             "Se usa para conservar el nombre aunque el producto cambie.",
    )
    quantity = fields.Float(
        string="Cantidad",
        required=True,
        default=1.0,
        digits="Product Unit of Measure",
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unidad de medida",
        ondelete="set null",
    )

    # ─── Notas y trazabilidad ─────────────────────────────────────────────────

    line_note = fields.Char(
        string="Nota de línea",
        help="Indicaciones especiales para este ítem (sin cebolla, extra picante, etc.).",
    )

    # Almacena el UUID de la línea de POS de origen para trazabilidad futura,
    # sin requerir el módulo point_of_sale instalado.
    source_pos_line_uuid = fields.Char(
        string="UUID línea POS",
        copy=False,
        help="Identificador único de la línea en el Punto de Venta. "
             "Se usa para trazabilidad al integrar con el módulo POS.",
    )

    # ─── Estado de la línea ───────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("preparing", "En preparación"),
            ("done", "Lista"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="pending",
        required=True,
        # El tracking se gestiona a nivel de orden, no de línea
    )

    # ─── Estado relacional (heredado de la orden) ─────────────────────────────

    kitchen_order_state = fields.Selection(
        related="kitchen_order_id.state",
        string="Estado de la orden",
        store=False,
    )

    # ─── Onchange: autocompletar nombre y UoM del producto ────────────────────

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_name = self.product_id.name
            self.uom_id = self.product_id.uom_id
        else:
            self.product_name = False
            self.uom_id = False

    # ─── Nombre display ───────────────────────────────────────────────────────

    def name_get(self):
        result = []
        for line in self:
            name = line.product_name or (line.product_id.name if line.product_id else _("Línea"))
            if line.line_note:
                name = f"{name} ({line.line_note})"
            result.append((line.id, name))
        return result
