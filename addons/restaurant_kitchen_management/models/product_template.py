from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    kitchen_preparable = fields.Boolean(
        string="Enviar a cocina",
        default=False,
        help="Si esta marcado, este producto generara una linea en la orden de cocina cuando se envie desde POS o delivery.",
    )
    kitchen_default_note = fields.Char(
        string="Nota por defecto para cocina",
    )
