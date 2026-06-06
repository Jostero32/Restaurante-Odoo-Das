{
    "name": "Ecuador - Facturación Electrónica SRI",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Integración con el SRI para emisión de comprobantes electrónicos en Ecuador",
    "author": "ARCM Solutions",
    "license": "LGPL-3",
    "depends": [
        "account",
        "l10n_ec",
        "l10n_latam_invoice_document",
        "point_of_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_ec_certificate_views.xml",
        "views/res_company_views.xml",
        "views/account_move_views.xml",
    ],
    "external_dependencies": {
        "python": ["cryptography", "lxml"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
