import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    _crypto_ok = True
except ImportError:
    _crypto_ok = False


class L10nEcCertificate(models.Model):
    _name = "l10n_ec.certificate"
    _description = "Certificado Digital SRI (.p12)"

    name = fields.Char("Nombre", required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company
    )
    content = fields.Binary("Archivo .p12", required=True, attachment=False)
    file_name = fields.Char("Nombre del archivo")
    password = fields.Char("Contraseña del certificado")
    subject_cn = fields.Char("Titular", readonly=True)
    date_start = fields.Date("Válido desde", readonly=True)
    date_end = fields.Date("Válido hasta", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Sin validar"),
            ("active", "Activo"),
            ("expired", "Vencido"),
            ("invalid", "Inválido"),
        ],
        default="draft",
        string="Estado",
    )

    def action_validate(self):
        for rec in self:
            if not _crypto_ok:
                raise UserError(
                    _("La librería 'cryptography' no está disponible en el servidor.")
                )
            if not rec.content:
                raise UserError(_("Suba un archivo .p12 primero."))
            try:
                p12_bytes = base64.b64decode(rec.content)
                pw = rec.password.encode("utf-8") if rec.password else None
                _pk, cert, _chain = pkcs12.load_key_and_certificates(p12_bytes, pw)

                try:
                    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                except Exception:
                    cn = str(cert.subject)

                # not_valid_before_utc se añadió en cryptography 42; fallback para 41.x
                try:
                    not_before = cert.not_valid_before_utc.date()
                    not_after = cert.not_valid_after_utc.date()
                except AttributeError:
                    not_before = cert.not_valid_before.date()
                    not_after = cert.not_valid_after.date()

                today = fields.Date.today()

                rec.subject_cn = cn
                rec.date_start = not_before
                rec.date_end = not_after
                rec.state = "active" if not_after >= today else "expired"

            except UserError:
                raise
            except Exception as e:
                rec.state = "invalid"
                raise UserError(_("Certificado inválido: %s") % str(e))
