# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
import json

_logger = logging.getLogger(__name__)

# Metodo que hace la herencia del modelo de transaccion de pago para agregar los campos necesarios para kushki, ademas de agregar los metodos necesarios para el manejo de las transacciones de pago con kushki
class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    kushki_type = fields.Char(string="Kushki Transaction Type")

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Kushki-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """

        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'kushki':
            return res

        partner_first_name, partner_last_name = payment_utils.split_partner_name(self.partner_name)
        _url = '/kushki_confirm/?total={}'.format(self.amount)

        lines = []
        for line in self.sale_order_ids.order_line.product_id:
            lines.append({
                'id': str(line['id']),
                'code': line['code'],
                'name': line['name'],
                'list_price': line['list_price'],
                'description_sale': line['description_sale'],
                'product_variant_count': line['product_variant_count'],
            })
        data = {
            'kushki_publicmerchantmd': self.provider_id.kushki_publicmerchantmd,
            'kushki_privatemerchantmd': self.provider_id.kushki_privatemerchantmd,
            'kushki_kformid': self.provider_id.kushki_kformid,
            'kushki_intestenvironment': self.provider_id.kushki_intestenvironment,
            'kushki_url': self.provider_id.kushki_url,
            'kushki_sitedomain': self.provider_id.kushki_sitedomain,
            'kushki_url_otp': self.provider_id.kushki_url_otp,

            'amount': self.amount,
            'business': self.partner_id.email,
            'city': self.partner_city,
            'country': self.partner_country_id.code,
            'currency_code': self.currency_id.name,
            'email': self.partner_email,
            'first_name': partner_first_name,
            'item_name': f"{self.company_id.name}: {self.reference}",
            'item_number': self.reference,
            'last_name': partner_last_name,
            'lc': self.partner_lang,
            'state': self.partner_state_id.name,
            'zip_code': self.partner_zip,
            'phone': self.partner_id.phone,
            'street': self.partner_id.street,
            'street2': self.partner_id.street2,
            'nif': self.partner_id.vat,

            'url': '/payment_kushki/paid', #_url
            'payment_transaction_id': self.id,
            'lines': json.dumps(lines),
        }
        return data

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on Mercado Pago data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If inconsistent data were received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'kushki' or len(tx) == 1:
            return tx

        reference = notification_data.get('external_reference')
        if not reference:
            raise ValidationError("Kushki: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'kushki')])
        if not tx:
            raise ValidationError(
                "Kushki: " + _("No transaction found matching reference %s.", reference)
            )
        return tx


    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on Kushki data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'kushki':
            return

        txn_id = notification_data.get('ticketNumber')
        txn_type = notification_data.get('transactionReference')
        #txn_id = notification_data.get('txn_id')
        #txn_type = notification_data.get('txn_type')
        if not all((txn_id, txn_type)):
            raise ValidationError(
                "Kushki: " + _(
                    "Missing value for ticketNumber (%(txn_id)s) or transactionReference (%(txn_type)s).",
                    txn_id=txn_id, txn_type=txn_type
                )
            )
        self.provider_reference = txn_id
        self.paypal_type = txn_type
        self.provider_reference = notification_data['transactionReference']

        payment_status = notification_data['details']['transactionStatus']

        if payment_status == 'APPROVAL':
            #sale.orde (action_confirm, invoiced, action_quotation_send)
            #self._set_pending()
            self._set_done()
        else:
            self._set_canceled()
            _logger.info(
                "received data with invalid payment status (%s) for transaction with reference %s",
                payment_status, self.reference
            )
            self._set_error(
                "Kushki: " + _("Received data with invalid payment status: %s", payment_status)
            )
