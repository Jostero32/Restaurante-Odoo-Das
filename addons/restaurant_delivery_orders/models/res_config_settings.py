from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Moneda de la compania",
        readonly=True,
    )
    delivery_fixed_fee = fields.Monetary(
        related="company_id.delivery_fixed_fee",
        currency_field="company_currency_id",
        readonly=False,
        string="Costo fijo de envio",
    )
    delivery_fee_product_id = fields.Many2one(
        related="company_id.delivery_fee_product_id",
        readonly=False,
        string="Producto costo de envio",
        domain="[('sale_ok', '=', True), ('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
