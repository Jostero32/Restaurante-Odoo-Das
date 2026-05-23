from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    delivery_eta_min = fields.Integer(
        string="Delivery ETA minimo (min)",
        default=35,
        help="Tiempo estimado minimo de entrega para mostrar en la web.",
    )
    delivery_eta_max = fields.Integer(
        string="Delivery ETA maximo (min)",
        default=50,
        help="Tiempo estimado maximo de entrega para mostrar en la web.",
    )
    delivery_portion_label = fields.Char(
        string="Tamano / porcion (web)",
        default="1+ persona",
        translate=True,
        help="Texto breve de porcion mostrado como KPI en la ficha del producto.",
    )
    delivery_payment_coverage_note = fields.Char(
        string="Pagos y cobertura (web)",
        default="Segun direccion en checkout",
        translate=True,
        help="Resumen corto de pagos y cobertura mostrado como KPI.",
    )
    delivery_ingredients = fields.Text(
        string="Ingredientes (web)",
        translate=True,
        help="Se muestra en el desplegable de ingredientes.",
    )
    delivery_allergens = fields.Text(
        string="Alergenos (web)",
        translate=True,
        help="Se muestra en el desplegable de ingredientes/alergenos.",
    )
    delivery_incidents_policy = fields.Text(
        string="Incidencias (web)",
        translate=True,
        help="Texto para el desplegable de incidencias del pedido.",
    )

    @api.constrains("delivery_eta_min", "delivery_eta_max")
    def _check_delivery_eta_range(self):
        for product in self:
            if product.delivery_eta_min < 0 or product.delivery_eta_max < 0:
                raise ValidationError("El ETA de delivery no puede ser negativo.")
            if product.delivery_eta_min > product.delivery_eta_max:
                raise ValidationError("El ETA minimo no puede ser mayor al ETA maximo.")
