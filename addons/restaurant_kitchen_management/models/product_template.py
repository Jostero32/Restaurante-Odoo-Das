from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    kitchen_preparable = fields.Boolean(
        string="Enviar a cocina",
        default=False,
        help="Si está activo, este producto aparece disponible para ser incluido "
             "en las órdenes de cocina del módulo de gestión de cocina.",
    )
