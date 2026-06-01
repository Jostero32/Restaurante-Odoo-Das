from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_delivery_fee = fields.Boolean(
        string="Linea costo delivery",
        default=False,
        copy=False,
        help="Identifica la linea tecnica del costo de envio configurado para delivery.",
    )

    def _orders_requiring_delivery_sync(self):
        orders = self.mapped("order_id")
        return orders.filtered(lambda order: order.delivery_order_id or order._is_delivery_sync_candidate())

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if self.env.context.get("skip_delivery_line_sync"):
            return lines
        lines._orders_requiring_delivery_sync()._sync_delivery_order_from_sale()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_delivery_line_sync"):
            return result
        tracked_fields = {
            "product_id",
            "name",
            "product_uom_qty",
            "product_uom",
            "price_unit",
            "discount",
            "tax_id",
            "display_type",
        }
        if tracked_fields.intersection(vals):
            self._orders_requiring_delivery_sync()._sync_delivery_order_from_sale()
        return result

    def unlink(self):
        orders = self._orders_requiring_delivery_sync()
        result = super().unlink()
        if self.env.context.get("skip_delivery_line_sync"):
            return result
        orders._sync_delivery_order_from_sale()
        return result
