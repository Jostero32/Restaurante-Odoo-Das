# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import json
import unicodedata
import requests
from datetime import datetime
from werkzeug.exceptions import Forbidden

_logger = logging.getLogger(__name__)

class PaymentKushki(http.Controller):
    @http.route(['/payment_kushki/paid'], methods=['POST'], auth="user", website=True)
    def payment_kushki_paid(self, **kw):
        """
        Build data to render Kajita...
        """

        argument = request.params
        _url = '/kushki_confirm/?total={}'.format(argument['amount'])
        data = {
            'kushki_publicmerchantmd': argument['kushki_publicmerchantmd'],
            'kushki_privatemerchantmd': argument['kushki_privatemerchantmd'],
            'kushki_kformid': argument['kushki_kformid'],
            'kushki_intestenvironment': argument['kushki_intestenvironment'],
            'kushki_url': argument['kushki_url'],
            'kushki_sitedomain': argument['kushki_sitedomain'],
            'kushki_url_otp': argument['kushki_url_otp'],
            'amount': argument['amount'],
            'business': argument['business'],
            'city': argument['city'],
            'country': argument['country'],
            'currency_code': argument['currency_code'],
            'email': argument['email'],
            'first_name': argument['first_name'],
            'item_name': argument['item_name'],
            'item_number': argument['item_number'],
            'last_name': argument['last_name'],
            'lc': argument['lc'],
            'state': argument['state'],
            'zip_code': argument['zip_code'],
            'phone': argument['phone'],
            'street': argument['street'],
            'street2': argument['street2'],
            'nif': argument['nif'],
            'url': _url,
            'payment_transaction_id': argument['payment_transaction_id'],
            'lines': argument['lines'],

        }
        return http.request.render('pay_kushki.kushki', data)

    def build_paid_data(self, argument):
        """
        Constrir objeto para enviar en la solicitud del pago ..
        """
        params = request.env['payment.provider'].sudo().search([('code', '=', 'kushki')])

        total = float(str(argument['amount']))
        topaid = json.loads(argument['lines'])
        product = []

        for row in topaid:
            #data = ast.literal_eval(row)
            product.append({
                'id': str(row['id']),
                'title': row['name'],
                'price': int(row['list_price'] * 1000000),
                'sku': str(row['code']),
                'quantity': row['product_variant_count']
            })
            #personal_id = data['clientId']

        # get account data
        #account_data = self.get_account_data(personal_id)

        #client = account_data[0]['client'][0]
        address = (argument['street'] if argument['street'] else ' ') + ' ' + (
            ' y ' + argument['street2'] if argument['street2'] else ' ')
        first_name, last_name = argument['first_name'], argument['last_name']

        # documentType
        documentType = {'1': 'RUC', '2': 'CI', '3': 'PAS'}

        # phoneNumber
        phoneNumber = argument['phone'].replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if len(phoneNumber) != 12:
            phoneNumber.ljust(12, '1')

        payload = {
            "token": unicodedata.normalize('NFKD', argument['kushkiToken']).encode('ascii', 'ignore').decode("utf-8"),
            "amount": {
                "subtotalIva": 0,
                "subtotalIva0": total,
                "ice": 0,
                "iva": 0,
                "currency": argument['currency_code']
            },
            # "deferred":{
            #             "graceMonths":"02",
            #             "creditType":"01",
            #             "months":3
            # },
            "metadata": {
                "external_reference": argument['item_number']
            },
            "contactDetails": {
                "documentType": 'PAS',
                "documentNumber": argument['nif'] if argument['nif'] else '',
                "email": argument['email'] if argument['email'] else 'test@test.com',
                "firstName": first_name,
                "lastName": last_name,
                "phoneNumber": phoneNumber,
            },
            "orderDetails": {
                "siteDomain": params[0]['kushki_sitedomain'].strip(),
                # "shippingDetails": {
                #     "name": client['name'] if client['name'] else '',
                #     "phone": client['phone'] if client['phone'] else '+593000000000',
                #     "address": address,
                #     "city": client['city'] if client['city'] else '',
                #     "region": client['state_id'][1] if client['state_id'] else '',
                #     "country": client['country_id'][1] if client['country_id'] else '',
                #     "zipCode": client['zip'] if client['zip'] else ''
                # },
                "billingDetails": {
                    "name": first_name + ' ' + last_name,
                    "phone": phoneNumber,
                    "address1": address,
                    "city": argument['city'] if argument['city'] else '',
                    "region": argument['lc'] if argument['lc'] else '',
                    "country": argument['country'] if argument['country'] else '',
                    "zipCode": argument['zip_code'] if argument['zip_code'] else ''
                }
            },
            "fullResponse": "v2",
            "productDetails": {
                "product": product
            }
        }

        return payload

    @http.route(['/kushki_confirm'], auth="public", website=True)
    def kushki_confirm(self, **kw):
        """
        Cinfirmar pago en kushki
        """
        argument = request.params
        if eval(request.params.get('parameters', '{}')):
            argument = eval(request.params.get('parameters', '{}'))
        params = request.env['payment.provider'].sudo().search([('code', '=', 'kushki')])

        # validación OTP (Se encarga la kajita sola de solicitar los datos y de las validaciones...)
        # https://api-uat.kushkipagos.com/rules/v1/secureValidation

        # Procesar pago
        # https://api-uat.kushkipagos.com/card/v1/charges
        url = params[0]['kushki_url']
        payload = self.build_paid_data(argument)
        data_json = json.dumps(payload)

        # return True
        # Numero de telefono y correo del cliente requeridos ...

        headers = {'content-type': 'application/json',
                   'Private-Merchant-Id': params[0]['kushki_privatemerchantmd']
                   }
        #self.set_log('request_payment', data_json)
        response = requests.request("POST", url, data=data_json, headers=headers)
        #self.set_log('response_payment', response.text)

        response_text = unicodedata.normalize('NFKD', response.text).encode('ascii', 'ignore')
        response_text = json.loads(response_text)

        result = []
        ticket = response_text.get('ticketNumber', False)

        if ticket:
            # Cobro Satisfactorio
            ticket = response_text['ticketNumber']

            #finish payment un odoo..
            # Check the origin of the notification
            data = {'external_reference': argument['item_number']}
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'kushki', data
            )

            # Handle the notification data
            tx_sudo._process_notification_data(response_text)

            # Confirm sale order immediately to create the delivery order.
            # Full accounting post-processing (payment recording) is handled
            # asynchronously by Odoo's _cron_post_process scheduled action.
            if tx_sudo.state == 'done':
                tx_sudo.sale_order_ids.filtered(
                    lambda so: so.state in ('draft', 'sent')
                ).with_context(send_email=True).action_confirm()

        else:
            # Cobro no Autorizado
            result.append({'key': 'message', 'value': response_text['message']})

        #print('response_text', response_text)

        return http.request.render('pay_kushki.kushki_result', {
            'response_text': response_text,
            'ticket': ticket,
            'date': datetime.today().strftime('%d/%m/%Y %H:%M:%S')
        })
