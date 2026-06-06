import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_CONSUMIDOR_FINAL_VAT = "9999999999999"


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_pos_order_paid(self):
        result = super().action_pos_order_paid()
        company = self.env.company
        if not company.l10n_ec_auto_send_sri:
            return result
        cert = company.l10n_ec_certificate_id
        if not cert or cert.state != "active":
            return result
        consumidor = self._sri_get_or_create_consumidor_final()
        for order in self:
            if order.account_move:
                continue
            if not order.partner_id:
                order.sudo().write({"partner_id": consumidor.id})
            try:
                order.sudo().action_pos_order_invoice()
            except Exception:
                _logger.warning(
                    "No se pudo generar factura SRI para orden POS %s",
                    order.name,
                    exc_info=True,
                )
        return result

    @api.model
    def _sri_get_or_create_consumidor_final(self):
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search(
            [("vat", "=", _CONSUMIDOR_FINAL_VAT)], limit=1
        )
        if not partner:
            partner = Partner.create(
                {
                    "name": "CONSUMIDOR FINAL",
                    "vat": _CONSUMIDOR_FINAL_VAT,
                    "customer_rank": 1,
                }
            )
        return partner
