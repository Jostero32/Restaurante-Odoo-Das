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
    restaurant_delivery_carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Carrier delivery restaurante",
        copy=False,
        help="Carrier de Odoo gestionado automáticamente para mostrar el costo de envío en el checkout.",
    )

    def write(self, vals):
        result = super().write(vals)
        if {"delivery_fixed_fee", "delivery_fee_product_id"}.intersection(vals):
            for company in self:
                company._sync_restaurant_delivery_carrier()
        return result

    def _sync_restaurant_delivery_carrier(self):
        """Crea o actualiza el delivery.carrier de Odoo sincronizado con nuestro fee fijo."""
        product = self.delivery_fee_product_id
        if not product:
            return

        fee = self.delivery_fixed_fee or 0.0

        Carrier = self.env["delivery.carrier"].sudo()
        carrier = self.restaurant_delivery_carrier_id

        if carrier:
            carrier.write({
                "product_id": product.id,
                "fixed_price": fee,
                "active": True,
            })
        else:
            carrier = Carrier.create({
                "name": "Envío a domicilio",
                "delivery_type": "fixed",
                "product_id": product.id,
                "fixed_price": fee,
                "is_published": True,
            })
            self.sudo().restaurant_delivery_carrier_id = carrier

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
