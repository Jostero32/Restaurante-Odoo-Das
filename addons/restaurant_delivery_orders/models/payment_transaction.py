import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _set_done(self, **kwargs):
        result = super()._set_done(**kwargs)
        self.sudo()._finalize_delivery_orders_on_payment()
        # Post-procesar inmediatamente: crea account.payment y reconcilia con la factura.
        # Sin esto, queda como "crédito pendiente" hasta que corra el cron.
        for tx in self:
            try:
                with self.env.cr.savepoint():
                    tx.sudo()._post_process()
            except Exception:
                _logger.warning(
                    "Error en post-process inmediato de tx %s", tx.reference, exc_info=True
                )
        return result

    def _set_pending(self, state_message=None, **kwargs):
        result = super()._set_pending(state_message=state_message, **kwargs)
        # Sin webhook (local o producción sin dominio) → auto-confirmar Kushki
        for tx in self:
            if tx.provider_code == "kushki":
                try:
                    with self.env.cr.savepoint():
                        tx._set_done()
                except Exception:
                    _logger.warning(
                        "No se pudo auto-confirmar tx Kushki %s en modo prueba",
                        tx.reference, exc_info=True,
                    )
        return result

    def _finalize_delivery_orders_on_payment(self):
        """Al confirmar el pago, valida y envia la factura de inmediato para pedidos de ecommerce."""
        for tx in self:
            ecommerce_orders = tx.sale_order_ids.filtered(
                lambda so: bool(so.website_id) and so.state != "cancel"
            )
            if not ecommerce_orders:
                continue

            # Confirmar ordenes pendientes individualmente con savepoint para que el fallo
            # de una orden no descarte las demas ni corrompa la transaccion principal.
            pending = ecommerce_orders.filtered(lambda so: so.state in {"draft", "sent"})
            for order in pending:
                try:
                    with order.env.cr.savepoint():
                        order.with_context(
                            skip_slot_validation=True,
                            send_email=True,
                        ).action_confirm()
                except Exception:
                    _logger.exception(
                        "Error al confirmar pedido %s tras pago %s",
                        order.name,
                        tx.reference,
                    )
                    self._post_payment_alert(
                        order,
                        _(
                            "El pedido no se pudo confirmar automaticamente tras el cobro "
                            "(referencia de pago: %(ref)s). Verificar y confirmar manualmente."
                        ) % {"ref": tx.reference or ""},
                    )

            # Facturar todos los pedidos ya confirmados, incluso si alguno no se pudo confirmar.
            confirmed = ecommerce_orders.filtered(lambda so: so.state == "sale")
            if not confirmed:
                continue

            try:
                with confirmed.env.cr.savepoint():
                    confirmed.with_context(
                        skip_delivery_sync=True
                    ).action_finalize_delivery_invoicing()
            except Exception:
                _logger.exception(
                    "Error al finalizar facturacion para pedidos %s tras pago %s",
                    confirmed.ids,
                    tx.reference,
                )
                for order in confirmed:
                    self._post_payment_alert(
                        order,
                        _(
                            "La factura no se pudo generar automaticamente tras el cobro "
                            "(referencia: %(ref)s). Verificar manualmente en contabilidad."
                        ) % {"ref": tx.reference or ""},
                    )

    @staticmethod
    def _post_payment_alert(sale_order, body):
        """Publica una nota interna en el pedido para que el equipo vea el problema."""
        try:
            sale_order.sudo().message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            _logger.warning(
                "No se pudo publicar alerta en pedido %s: %s",
                getattr(sale_order, "name", "?"),
                body,
            )
