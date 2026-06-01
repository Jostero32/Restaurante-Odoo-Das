from odoo import _, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    reservation_id = fields.Many2one(
        "restaurant.table.reservation",
        string="Reserva origen",
        copy=False,
        readonly=True,
        help="Linea inyectada al POS desde el pre-pedido de una reserva.",
    )

    def unlink(self):
        for line in self.filtered(lambda l: l.reservation_id):
            line.reservation_id.sudo().message_post(
                body=_(
                    "Ajuste manual: se elimino en POS una linea del pre-pedido "
                    "(%(qty)s x %(product)s) de la orden %(order)s."
                )
                % {
                    "qty": line.qty,
                    "product": line.product_id.display_name,
                    "order": line.order_id.name or line.order_id.pos_reference or line.order_id.id,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        return super().unlink()
