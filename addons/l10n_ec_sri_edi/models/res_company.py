from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ec_sri_environment = fields.Selection(
        [("1", "Pruebas"), ("2", "Producción")],
        string="Ambiente SRI",
        default="1",
    )
    l10n_ec_certificate_id = fields.Many2one(
        "l10n_ec.certificate",
        string="Certificado Digital",
        domain="[('company_id', '=', id), ('state', '=', 'active')]",
    )
    l10n_ec_establec = fields.Char(
        "Establecimiento SRI", default="001", size=3,
        help="Código de 3 dígitos del establecimiento registrado en el SRI (ej. 001)"
    )
    l10n_ec_pto_emision = fields.Char(
        "Punto de Emisión SRI", default="001", size=3,
        help="Código de 3 dígitos del punto de emisión registrado en el SRI (ej. 001)"
    )
    l10n_ec_auto_send_sri = fields.Boolean(
        "Enviar al SRI automáticamente al confirmar",
        default=False,
        help="Si está activo, las facturas de clientes se envían al SRI automáticamente "
             "al momento de confirmarlas. Los errores se registran en la factura sin bloquear."
    )
