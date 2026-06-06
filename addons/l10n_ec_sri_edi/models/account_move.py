import base64
import logging
import random
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from lxml import etree
    _lxml_ok = True
except ImportError:
    _lxml_ok = False


def _e(parent, tag, text=""):
    """Helper: añade un subelemento con texto al padre."""
    el = etree.SubElement(parent, tag)
    el.text = str(text) if text is not None else ""
    return el


def _fmt(val, decimals=2):
    return f"{val:.{decimals}f}"


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ec_sri_access_key = fields.Char(
        "Clave de Acceso SRI", size=49, copy=False, readonly=True, index=True
    )
    l10n_ec_sri_authorization_number = fields.Char(
        "Número de Autorización", copy=False, readonly=True
    )
    l10n_ec_sri_authorization_date = fields.Datetime(
        "Fecha Autorización SRI", copy=False, readonly=True
    )
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "No enviado"),
            ("sent", "Enviado / Pendiente"),
            ("authorized", "Autorizado"),
            ("rejected", "Rechazado"),
            ("cancelled", "Anulado"),
        ],
        default="draft",
        string="Estado SRI",
        copy=False,
        readonly=True,
        tracking=True,
    )
    l10n_ec_sri_response = fields.Text("Respuesta SRI", copy=False, readonly=True)
    l10n_ec_xml_file = fields.Binary("XML Firmado", attachment=True, copy=False, readonly=True)
    l10n_ec_xml_filename = fields.Char(copy=False, readonly=True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sri_is_ec_invoice(self):
        return (
            self.move_type in ("out_invoice", "out_refund")
            and self.company_id.country_id.code == "EC"
        )

    def _sri_seq_parts(self):
        """Devuelve (establec, pto_emi, secuencial_9_digitos)."""
        company = self.company_id
        establec = (company.l10n_ec_establec or "001").zfill(3)[:3]
        pto_emi = (company.l10n_ec_pto_emision or "001").zfill(3)[:3]
        # Intenta extraer el número secuencial del nombre de la factura
        name = self.name or ""
        parts = name.split("/")
        try:
            seq = str(int(parts[-1])).zfill(9)
        except (ValueError, IndexError):
            seq = "000000001"
        return establec, pto_emi, seq

    @staticmethod
    def _modulo11(key_48):
        """Calcula el dígito verificador Módulo 11 para la clave de acceso SRI."""
        factors = [2, 3, 4, 5, 6, 7]
        total = sum(int(d) * factors[i % 6] for i, d in enumerate(reversed(key_48)))
        residuo = total % 11
        v = 11 - residuo
        if v == 11:
            return 0
        if v == 10:
            return 1
        return v

    def _generate_access_key(self):
        """Genera la clave de acceso de 49 dígitos y la almacena en el registro."""
        company = self.company_id
        env_code = company.l10n_ec_sri_environment or "1"
        emission_date = self.invoice_date or fields.Date.today()
        doc_type = "01" if self.move_type == "out_invoice" else "04"
        ruc = (company.vat or "9999999999999").replace("-", "").zfill(13)[:13]
        establec, pto_emi, seq = self._sri_seq_parts()
        cod_num = "".join(str(random.randint(0, 9)) for _ in range(8))

        base_key = (
            emission_date.strftime("%d%m%Y")  # 8
            + doc_type                         # 2
            + ruc                              # 13
            + env_code                         # 1
            + establec                         # 3
            + pto_emi                          # 3
            + seq                              # 9
            + cod_num                          # 8
            + "1"                              # 1 (emisión normal)
        )  # total = 48
        access_key = base_key + str(self._modulo11(base_key))
        self.l10n_ec_sri_access_key = access_key
        return access_key

    @staticmethod
    def _tax_sri_codes(tax):
        """
        Mapea un impuesto de Odoo a (codigo, codigoPorcentaje, tarifa) del SRI.
        Tabla 16 (código): 2=IVA, 3=ICE, 5=ISD
        Tabla 17 (codigoPorcentaje IVA): 0=0%, 2=12%, 3=14%, 4=15%, 5=5%, 6=no objeto, 7=exento
        """
        name = (tax.name or "").upper()
        if "ICE" in name:
            return ("3", "3023", "0.00")
        if "ISD" in name:
            return ("5", "5001", "0.00")
        for pct, codes in (
            ("15", ("2", "4", "15.00")),
            ("12", ("2", "2", "12.00")),
            ("14", ("2", "3", "14.00")),
            ("5%", ("2", "5", "5.00")),
        ):
            if pct in name:
                return codes
        if "NO OBJETO" in name or "NO_OBJETO" in name:
            return ("2", "6", "0.00")
        if "EXENTO" in name or "EXENTA" in name:
            return ("2", "7", "0.00")
        if "0%" in name or "IVA 0" in name or "IVA0" in name:
            return ("2", "0", "0.00")
        # Fallback: IVA 15%
        return ("2", "4", "15.00")

    def _get_partner_id_type(self, partner):
        if not partner:
            return "07"  # Consumidor Final
        vat = (partner.vat or "").replace("-", "").strip()
        if not vat or vat == "9999999999999":
            return "07"  # Consumidor Final
        if len(vat) == 13:
            return "04"  # RUC
        if len(vat) == 10:
            return "05"  # Cédula
        # Intentar desde l10n_latam_identification_type_id
        id_type = getattr(partner, "l10n_latam_identification_type_id", None)
        if id_type:
            nm = (id_type.name or "").lower()
            if "ruc" in nm:
                return "04"
            if "cedula" in nm or "cédula" in nm:
                return "05"
            if "pasaporte" in nm:
                return "06"
        return "08"  # Identificación exterior

    def _compute_tax_aggregates(self):
        tax_grouped = defaultdict(lambda: {"base": 0.0, "amount": 0.0})
        for line in self.invoice_line_ids:
            if line.display_type in ("line_section", "line_note"):
                continue
            price_r = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            for tax in line.tax_ids:
                codigo, cod_porc, _ = self._tax_sri_codes(tax)
                res = tax.compute_all(
                    price_r, quantity=line.quantity,
                    product=line.product_id, partner=self.partner_id,
                )
                key = (codigo, cod_porc)
                tax_grouped[key]["base"] += res["total_excluded"]
                tax_grouped[key]["amount"] += res["total_included"] - res["total_excluded"]
        return [
            {"codigo": k[0], "codigo_porcentaje": k[1], "base": v["base"], "amount": v["amount"]}
            for k, v in tax_grouped.items()
        ]

    # ── Generación del XML ────────────────────────────────────────────────────

    def _generate_sri_xml(self):
        if not _lxml_ok:
            raise UserError(_("lxml no está disponible en el servidor."))

        company = self.company_id
        partner = self.partner_id
        access_key = self.l10n_ec_sri_access_key or self._generate_access_key()
        emission_date = self.invoice_date or fields.Date.today()
        establec, pto_emi, seq = self._sri_seq_parts()

        root = etree.Element("factura")
        root.set("id", "comprobante")
        root.set("version", "1.0.0")

        # infoTributaria
        it = etree.SubElement(root, "infoTributaria")
        _e(it, "ambiente", company.l10n_ec_sri_environment or "1")
        _e(it, "tipoEmision", "1")
        _e(it, "razonSocial", company.name or "")
        _e(it, "nombreComercial", company.name or "")
        _e(it, "ruc", (company.vat or "").replace("-", "")[:13])
        _e(it, "claveAcceso", access_key)
        _e(it, "codDoc", "01" if self.move_type == "out_invoice" else "04")
        _e(it, "estab", establec)
        _e(it, "ptoEmi", pto_emi)
        _e(it, "secuencial", seq)
        _e(it, "dirMatriz", company.street or "S/N")

        # infoFactura
        ifac = etree.SubElement(root, "infoFactura")
        _e(ifac, "fechaEmision", emission_date.strftime("%d/%m/%Y"))
        _e(ifac, "dirEstablecimiento", company.street or "S/N")
        _e(ifac, "obligadoContabilidad", "SI")
        # Sin partner o sin RUC/cédula → Consumidor Final (tipo 07, RUC 9999999999999)
        _e(ifac, "tipoIdentificacionComprador", self._get_partner_id_type(partner))
        _e(ifac, "razonSocialComprador", (partner.name if partner else "") or "CONSUMIDOR FINAL")
        _e(ifac, "identificacionComprador", ((partner.vat or "") if partner else "").replace("-", "") or "9999999999999")

        total_discount = sum(
            line.price_unit * line.quantity * (line.discount or 0.0) / 100.0
            for line in self.invoice_line_ids
            if line.display_type not in ("line_section", "line_note")
        )
        _e(ifac, "totalSinImpuestos", _fmt(self.amount_untaxed))
        _e(ifac, "totalDescuento", _fmt(total_discount))

        tci = etree.SubElement(ifac, "totalConImpuestos")
        for agg in self._compute_tax_aggregates():
            ti = etree.SubElement(tci, "totalImpuesto")
            _e(ti, "codigo", agg["codigo"])
            _e(ti, "codigoPorcentaje", agg["codigo_porcentaje"])
            _e(ti, "baseImponible", _fmt(agg["base"]))
            _e(ti, "valor", _fmt(agg["amount"]))

        _e(ifac, "propina", "0.00")
        _e(ifac, "importeTotal", _fmt(self.amount_total))
        _e(ifac, "moneda", "DOLAR")

        pagos = etree.SubElement(ifac, "pagos")
        pago = etree.SubElement(pagos, "pago")
        _e(pago, "formaPago", "20")  # 20 = Otros
        _e(pago, "total", _fmt(self.amount_total))

        # detalles
        detalles = etree.SubElement(root, "detalles")
        for line in self.invoice_line_ids:
            if line.display_type in ("line_section", "line_note"):
                continue
            det = etree.SubElement(detalles, "detalle")
            _e(det, "codigoPrincipal", line.product_id.default_code or "GEN")
            desc = (line.name or line.product_id.name or "Producto").replace("\n", " ").strip()
            _e(det, "descripcion", desc)
            _e(det, "cantidad", _fmt(line.quantity, 6))
            _e(det, "precioUnitario", _fmt(line.price_unit, 6))
            disc_amt = line.price_unit * line.quantity * (line.discount or 0.0) / 100.0
            _e(det, "descuento", _fmt(disc_amt))
            base_no_tax = line.price_unit * line.quantity - disc_amt
            _e(det, "precioTotalSinImpuesto", _fmt(base_no_tax))

            impuestos = etree.SubElement(det, "impuestos")
            price_r = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            for tax in line.tax_ids:
                codigo, cod_porc, tarifa = self._tax_sri_codes(tax)
                res = tax.compute_all(
                    price_r, quantity=line.quantity,
                    product=line.product_id, partner=self.partner_id,
                )
                imp = etree.SubElement(impuestos, "impuesto")
                _e(imp, "codigo", codigo)
                _e(imp, "codigoPorcentaje", cod_porc)
                _e(imp, "tarifa", tarifa)
                _e(imp, "baseImponible", _fmt(res["total_excluded"]))
                _e(imp, "valor", _fmt(res["total_included"] - res["total_excluded"]))

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")

    # ── Acciones de la interfaz ───────────────────────────────────────────────

    def action_post(self):
        result = super().action_post()
        for move in self:
            if not move._sri_is_ec_invoice():
                continue
            company = move.company_id
            if not company.l10n_ec_auto_send_sri:
                continue
            cert = company.l10n_ec_certificate_id
            if not cert or cert.state != "active":
                continue
            try:
                move._sri_auto_send()
            except Exception as e:
                _logger.error("Error auto-enviando %s al SRI: %s", move.name, str(e))
                move.l10n_ec_sri_response = f"Error en auto-envío: {str(e)}"
        return result

    def _sri_auto_send(self):
        """Envía al SRI sin devolver notificación UI (para uso automático)."""
        if not self.l10n_ec_sri_access_key:
            self._generate_access_key()

        xml_bytes = self._generate_sri_xml()
        cert = self.company_id.l10n_ec_certificate_id
        signed_xml = self.env["l10n_ec.sri.signer"].sign_xml(
            xml_bytes, cert.content, cert.password or ""
        )

        env_code = self.company_id.l10n_ec_sri_environment or "1"
        response = self.env["l10n_ec.sri.service"].send_document(signed_xml, env_code)

        self.l10n_ec_xml_file = base64.b64encode(signed_xml)
        self.l10n_ec_xml_filename = f"factura_{self.l10n_ec_sri_access_key}.xml"

        status = response.get("status", "")
        msgs = "\n".join(response.get("messages", []))
        self.l10n_ec_sri_response = f"{status}\n{msgs}".strip()
        self.l10n_ec_sri_status = "sent" if status in ("RECIBIDA", "RECEIVED") else "rejected"

    def action_send_sri(self):
        self.ensure_one()
        if not self._sri_is_ec_invoice():
            raise UserError(_("Solo se pueden enviar facturas ecuatorianas al SRI."))
        if self.state != "posted":
            raise UserError(_("La factura debe estar confirmada antes de enviar al SRI."))

        cert = self.company_id.l10n_ec_certificate_id
        if not cert or cert.state != "active":
            raise UserError(
                _("Configure un certificado digital activo en la empresa (Configuración › SRI Ecuador).")
            )

        if not self.l10n_ec_sri_access_key:
            self._generate_access_key()

        xml_bytes = self._generate_sri_xml()

        signed_xml = self.env["l10n_ec.sri.signer"].sign_xml(
            xml_bytes, cert.content, cert.password or ""
        )

        env_code = self.company_id.l10n_ec_sri_environment or "1"
        response = self.env["l10n_ec.sri.service"].send_document(signed_xml, env_code)

        self.l10n_ec_xml_file = base64.b64encode(signed_xml)
        self.l10n_ec_xml_filename = f"factura_{self.l10n_ec_sri_access_key}.xml"

        status = response.get("status", "")
        msgs = "\n".join(response.get("messages", []))
        self.l10n_ec_sri_response = f"{status}\n{msgs}".strip()

        if status in ("RECIBIDA", "RECEIVED"):
            self.l10n_ec_sri_status = "sent"
            notif_type, notif_msg = "success", _(
                "Comprobante RECIBIDO por el SRI. Use 'Consultar Autorización' en unos minutos."
            )
        else:
            self.l10n_ec_sri_status = "rejected"
            notif_type, notif_msg = "danger", self.l10n_ec_sri_response

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SRI – Envío"),
                "message": notif_msg,
                "type": notif_type,
                "sticky": notif_type == "danger",
            },
        }

    def action_batch_send_sri(self):
        """Envía al SRI todas las facturas seleccionadas que estén publicadas y no enviadas."""
        candidates = self.filtered(
            lambda m: m._sri_is_ec_invoice()
            and m.state == "posted"
            and m.l10n_ec_sri_status in ("draft", "rejected")
        )
        sent, errors = 0, []
        for move in candidates:
            try:
                move._sri_auto_send()
                sent += 1
            except Exception as e:
                errors.append(f"{move.name}: {e}")
                _logger.warning("Error al enviar %s al SRI: %s", move.name, e)
        msg = _("Enviadas: %d.") % sent
        if errors:
            msg += "\n" + _("Errores: %s") % "\n".join(errors)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SRI – Envío masivo"),
                "message": msg,
                "type": "success" if not errors else "warning",
                "sticky": bool(errors),
            },
        }

    def action_check_authorization(self):
        self.ensure_one()
        if not self.l10n_ec_sri_access_key:
            raise UserError(_("No hay clave de acceso generada para este comprobante."))

        env_code = self.company_id.l10n_ec_sri_environment or "1"
        response = self.env["l10n_ec.sri.service"].check_authorization(
            self.l10n_ec_sri_access_key, env_code
        )

        status = response.get("status", "")
        msgs = "\n".join(response.get("messages", []))
        self.l10n_ec_sri_response = f"{status}\n{msgs}".strip()

        if status == "AUTORIZADO":
            self.l10n_ec_sri_status = "authorized"
            self.l10n_ec_sri_authorization_number = response.get("authorization_number")
            auth_date_str = response.get("authorization_date") or ""
            if auth_date_str:
                try:
                    from dateutil import parser as dtparser
                    self.l10n_ec_sri_authorization_date = dtparser.parse(auth_date_str)
                except Exception:
                    pass
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("SRI – Autorizado"),
                    "message": _("Número de autorización: %s") % self.l10n_ec_sri_authorization_number,
                    "type": "success",
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SRI – Estado: %s") % status,
                "message": msgs or _("Sin mensaje adicional del SRI."),
                "type": "warning",
                "sticky": True,
            },
        }
