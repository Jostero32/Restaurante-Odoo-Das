from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    delivery_fixed_fee = fields.Monetary(
        string="Costo fijo delivery",
        currency_field="currency_id",
        default=0.0,
        help="Tarifa fija de envio para pedidos delivery de ecommerce.",
    )
    delivery_fee_product_id = fields.Many2one(
        "product.product",
        string="Producto costo delivery",
        domain="[('sale_ok', '=', True), ('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', id)]",
        help="Producto de servicio usado para reflejar el costo de envio en la orden y factura.",
    )

    def _get_or_create_delivery_fee_product(self):
        self.ensure_one()
        if self.delivery_fee_product_id:
            return self.delivery_fee_product_id

        product = self.env["product.product"].create(
            {
                "name": "Costo de envio delivery",
                "type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "invoice_policy": "order",
                "company_id": self.id,
                "list_price": 0.0,
            }
        )
        self.delivery_fee_product_id = product
        return product
