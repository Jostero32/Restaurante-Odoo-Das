# -*- coding: utf-8 -*-
{
    'name': "Payment Provider: Kushki (Kajita)",
    'summary': "Payment with kushki in e-commerce store.",
    'description': """
        Integration of payment provider Kushki (kajita), in Odoo e-commerce store.
        Promote your sales by making it easier for your customers to pay digitally with cards.
    """,
    'author': "Dainier Escalona",
    'website': "https://www.odoodeb.com",
    'sequence': 450,
    'category': 'Accounting/Payment Providers',
    'version': '18.0.1.0.0',
    'depends': ['website_sale', 'payment', 'website_payment'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/payment_kushki_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',

        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            '/pay_kushki/static/src/js/kushki.js',
            'https://cdn.kushkipagos.com/kushki-checkout.js',
        ],
    },
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
    'support': 'odoodeb@gmail.com',
    'price': 0.0,
    'currency': 'USD',
    'images': ['static/src/img/main_screenshot.png', 'static/src/img/thumbnail.png'],
}
