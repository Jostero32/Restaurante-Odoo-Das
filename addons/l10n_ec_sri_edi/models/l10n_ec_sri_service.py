import base64
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
    from lxml import etree
    _libs_ok = True
except ImportError:
    _libs_ok = False

_RECEPTION_URLS = {
    "1": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline",
    "2": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline",
}
_AUTHORIZATION_URLS = {
    "1": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline",
    "2": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline",
}

_RECEPTION_TMPL = """\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ec="http://ec.gob.sri.ws.recepcion">
  <soapenv:Header/>
  <soapenv:Body>
    <ec:validarComprobante>
      <xml>{xml_b64}</xml>
    </ec:validarComprobante>
  </soapenv:Body>
</soapenv:Envelope>"""

_AUTH_TMPL = """\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ec="http://ec.gob.sri.ws.autorizacion">
  <soapenv:Header/>
  <soapenv:Body>
    <ec:autorizacionComprobante>
      <claveAccesoComprobante>{clave}</claveAccesoComprobante>
    </ec:autorizacionComprobante>
  </soapenv:Body>
</soapenv:Envelope>"""


class L10nEcSriService(models.AbstractModel):
    _name = "l10n_ec.sri.service"
    _description = "Servicio SOAP para envío de comprobantes al SRI Ecuador"

    def send_document(self, signed_xml_bytes, environment="1"):
        """Envía el XML firmado al SRI. Devuelve dict {status, messages}."""
        if not _libs_ok:
            raise UserError(_("La librería 'requests' no está disponible."))

        url = _RECEPTION_URLS.get(environment, _RECEPTION_URLS["1"])
        xml_b64 = base64.b64encode(signed_xml_bytes).decode()
        body = _RECEPTION_TMPL.format(xml_b64=xml_b64)

        try:
            resp = requests.post(
                url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
                timeout=30,
                verify=False,
            )
            resp.raise_for_status()
        except requests.Timeout:
            return {"status": "ERROR", "messages": ["Tiempo de espera agotado al contactar SRI."]}
        except Exception as e:
            return {"status": "ERROR", "messages": [str(e)]}

        return self._parse_reception(resp.text)

    def check_authorization(self, clave_acceso, environment="1"):
        """Consulta el estado de autorización de un comprobante. Devuelve dict."""
        if not _libs_ok:
            raise UserError(_("La librería 'requests' no está disponible."))

        url = _AUTHORIZATION_URLS.get(environment, _AUTHORIZATION_URLS["1"])
        body = _AUTH_TMPL.format(clave=clave_acceso)

        try:
            resp = requests.post(
                url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
                timeout=30,
                verify=False,
            )
            resp.raise_for_status()
        except requests.Timeout:
            return {"status": "ERROR", "messages": ["Tiempo de espera agotado al contactar SRI."]}
        except Exception as e:
            return {"status": "ERROR", "messages": [str(e)]}

        return self._parse_authorization(resp.text)

    @staticmethod
    def _parse_reception(xml_text):
        _logger.info("SRI recepción respuesta cruda:\n%s", xml_text)
        ns = "http://ec.gob.sri.ws.recepcion"
        try:
            root = etree.fromstring(xml_text.encode())
            # El body SRI no pone namespace en los hijos internos → buscar con y sin NS
            estado = root.find(f".//{{{ns}}}estado") or root.find(".//estado")

            mensajes = []
            # <mensaje> puede ser contenedor (tiene hijos) o hoja (tiene texto)
            for m in root.iter("mensaje"):
                if len(m) == 0 and m.text and m.text.strip():
                    mensajes.append(m.text.strip())
            for m in root.iter(f"{{{ns}}}mensaje"):
                if len(m) == 0 and m.text and m.text.strip():
                    mensajes.append(m.text.strip())
            for m in root.iter("informacionAdicional"):
                if m.text and m.text.strip():
                    mensajes.append(m.text.strip())

            status = estado.text.strip() if estado is not None else "DESCONOCIDO"
            _logger.info("SRI recepción estado=%s mensajes=%s", status, mensajes)
            return {"status": status, "messages": mensajes}
        except Exception as e:
            _logger.error("Error parseando respuesta de recepción SRI: %s\n%s", e, xml_text)
            return {"status": "ERROR", "messages": [str(e)]}

    @staticmethod
    def _parse_authorization(xml_text):
        _logger.info("SRI autorización respuesta cruda:\n%s", xml_text)
        ns = "http://ec.gob.sri.ws.autorizacion"
        try:
            root = etree.fromstring(xml_text.encode())
            estado = root.find(f".//{{{ns}}}estado") or root.find(".//estado")
            numero = root.find(f".//{{{ns}}}numeroAutorizacion") or root.find(".//numeroAutorizacion")
            fecha = root.find(f".//{{{ns}}}fechaAutorizacion") or root.find(".//fechaAutorizacion")

            mensajes = []
            for m in root.iter("mensaje"):
                if len(m) == 0 and m.text and m.text.strip():
                    mensajes.append(m.text.strip())
            for m in root.iter(f"{{{ns}}}mensaje"):
                if len(m) == 0 and m.text and m.text.strip():
                    mensajes.append(m.text.strip())

            status = estado.text.strip() if estado is not None else "DESCONOCIDO"
            _logger.info("SRI autorización estado=%s num=%s", status,
                         numero.text if numero is not None else None)
            return {
                "status": status,
                "authorization_number": numero.text if numero is not None else None,
                "authorization_date": fecha.text if fecha is not None else None,
                "messages": mensajes,
            }
        except Exception as e:
            _logger.error("Error parseando respuesta de autorización SRI: %s\n%s", e, xml_text)
            return {"status": "ERROR", "messages": [str(e)]}
