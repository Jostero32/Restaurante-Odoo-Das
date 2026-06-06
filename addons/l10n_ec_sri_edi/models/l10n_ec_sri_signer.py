import base64
import hashlib
import logging
from datetime import datetime, timezone

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from lxml import etree
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import pkcs12
    _libs_ok = True
except ImportError:
    _libs_ok = False


class L10nEcSriSigner(models.AbstractModel):
    _name = "l10n_ec.sri.signer"
    _description = "Firmador XAdES-BES para comprobantes SRI Ecuador"

    def sign_xml(self, xml_bytes, p12_binary, password):
        """
        Firma el XML con XAdES-BES (RSA-SHA1, C14N) según el estándar SRI Ecuador.
        Devuelve el XML firmado como bytes.
        """
        if not _libs_ok:
            raise UserError(
                _("Las librerías requeridas (cryptography, lxml) no están instaladas.")
            )

        # Odoo Binary fields devuelven bytes con la representación base64 (no el binario crudo)
        if isinstance(p12_binary, (str, bytes)):
            try:
                p12_binary = base64.b64decode(p12_binary)
            except Exception:
                pass
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")

        pw = password.encode("utf-8") if isinstance(password, str) and password else None

        try:
            private_key, certificate, _chain = pkcs12.load_key_and_certificates(p12_binary, pw)
        except Exception as e:
            raise UserError(_("Certificado inválido o contraseña incorrecta: %s") % str(e))

        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(xml_bytes, parser)

        ns_dsig = "http://www.w3.org/2000/09/xmldsig#"
        ns_xades = "http://uri.etsi.org/01903/v1.3.2#"

        # Digest del documento (SHA-1, C14N)
        xml_c14n = etree.tostring(root, method="c14n", exclusive=False, with_comments=False)
        doc_digest = base64.b64encode(hashlib.sha1(xml_c14n).digest()).decode()

        # SignedInfo
        signed_info = etree.Element(f"{{{ns_dsig}}}SignedInfo", nsmap={None: ns_dsig})
        c14n_m = etree.SubElement(signed_info, f"{{{ns_dsig}}}CanonicalizationMethod")
        c14n_m.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        sig_m = etree.SubElement(signed_info, f"{{{ns_dsig}}}SignatureMethod")
        sig_m.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#rsa-sha1")
        ref = etree.SubElement(signed_info, f"{{{ns_dsig}}}Reference")
        ref.set("URI", "#comprobante")
        ref.set("Type", "http://www.w3.org/2000/09/xmldsig#Object")
        transforms = etree.SubElement(ref, f"{{{ns_dsig}}}Transforms")
        tr = etree.SubElement(transforms, f"{{{ns_dsig}}}Transform")
        tr.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature")
        dm = etree.SubElement(ref, f"{{{ns_dsig}}}DigestMethod")
        dm.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")
        dv = etree.SubElement(ref, f"{{{ns_dsig}}}DigestValue")
        dv.text = doc_digest

        # Firmar SignedInfo (RSA-SHA1)
        signed_info_c14n = etree.tostring(signed_info, method="c14n", exclusive=False)
        sig_bytes = private_key.sign(signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
        sig_b64 = base64.b64encode(sig_bytes).decode()

        # KeyInfo (certificado DER)
        cert_b64 = base64.b64encode(
            certificate.public_bytes(serialization.Encoding.DER)
        ).decode()
        key_info = etree.Element(f"{{{ns_dsig}}}KeyInfo", nsmap={None: ns_dsig})
        x509d = etree.SubElement(key_info, f"{{{ns_dsig}}}X509Data")
        x509c = etree.SubElement(x509d, f"{{{ns_dsig}}}X509Certificate")
        x509c.text = cert_b64

        # Object / QualifyingProperties (XAdES-BES básico)
        obj_node = etree.Element(f"{{{ns_dsig}}}Object")
        qp = etree.SubElement(
            obj_node, f"{{{ns_xades}}}QualifyingProperties",
            nsmap={"xades": ns_xades}, Target="#Signature-SRI"
        )
        sp = etree.SubElement(qp, f"{{{ns_xades}}}SignedProperties", Id="SignedProperties")
        ssp = etree.SubElement(sp, f"{{{ns_xades}}}SignedSignatureProperties")
        st = etree.SubElement(ssp, f"{{{ns_xades}}}SigningTime")
        st.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Ensamble del nodo Signature
        sig_node = etree.Element(
            f"{{{ns_dsig}}}Signature", Id="Signature-SRI", nsmap={None: ns_dsig}
        )
        sig_node.append(signed_info)
        sig_val = etree.SubElement(sig_node, f"{{{ns_dsig}}}SignatureValue")
        sig_val.text = sig_b64
        sig_node.append(key_info)
        sig_node.append(obj_node)

        root.append(sig_node)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
