from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _orders_requiring_delivery_sync(self):
        orders = self.mapped("order_id")
        return orders.filtered(lambda order: order.delivery_order_id or order._is_delivery_sync_candidate())

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._orders_requiring_delivery_sync()._sync_delivery_order_from_sale()
        return lines

    def write(self, vals):
        result = super().write(vals)
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
        orders._sync_delivery_order_from_sale()
        return result
