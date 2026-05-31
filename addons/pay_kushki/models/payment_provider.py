# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from hashlib import new as hashnew

import requests

from odoo import _, api, fields, models
from .. import const

_logger = logging.getLogger(__name__)

#Metodo que hace la herencia del modelo de proveedor de pago para agregar los campos necesarios para kushki, ademas de agregar los metodos necesarios para el manejo de las transacciones de pago con kushki
class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('kushki', "Kushki")], ondelete={'kushki': 'set default'})
    kushki_publicmerchantmd = fields.Char(string='Public Merchantmd',
                help='kushki Public Merchantmd')
    kushki_privatemerchantmd = fields.Char(string='Private Merchantmd',
                help='Kushki Private Merchantmd')
    kushki_kformid = fields.Char(string='Kformid',
                help='Kajita Id Form')
    kushki_intestenvironment = fields.Boolean('Test Environment', default=True)
    kushki_url = fields.Char(string='URL',
                             default='https://api-uat.kushkipagos.com/card/v1/charges',
                            help='Kushki Url')
    kushki_sitedomain = fields.Char(string='Sitedomain',
                            default='mybusiness.com',
                            help='Kushki Sitedomain')
    kushki_url_otp = fields.Char(string='Url OTP',
                            default='https://api-uat.kushkipagos.com/rules/v1/secureValidation',
                            help='Kushki Url OTP')

    # === BUSINESS METHODS ===#

    @api.model
    def _get_compatible_providers(self, *args, is_validation=False, **kwargs):
        """ Override of payment to unlist Kushki providers for validation operations. """
        providers = super()._get_compatible_providers(*args, is_validation=is_validation, **kwargs)

        if is_validation:
            providers = providers.filtered(lambda p: p.code != 'kushki')

        return providers

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'kushki':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies
    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'kushki':
            return default_codes
        return const.DEFAULT_PAYMENT_METHODS_CODES