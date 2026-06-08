from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    kitchen_preparable = fields.Boolean(
        string="Enviar a cocina",
        default=False,
        help="Si esta marcado, este producto generara una linea en la orden de cocina cuando se envie desde POS o delivery.",
    )
    kitchen_default_note = fields.Char(
        string="Nota por defecto para cocina",
    )
    # Req 1: secuencia / pasos de preparacion
    kitchen_prep_steps = fields.Text(
        string="Secuencia de preparacion",
        help="Pasos a seguir para preparar el plato. Se muestran al cocinero en la orden.",
    )
    # Req 3: alergenos conocidos del plato
    kitchen_allergens = fields.Char(
        string="Alergenos / Contiene",
        help="Ingredientes alergenos que contiene el plato (ej: mani, gluten, lacteos).",
    )
    # Req 2: disponibilidad del dia ('86' del plato)
    kitchen_available_today = fields.Boolean(
        string="Disponible hoy",
        default=True,
        help="Si se desmarca, el plato se considera agotado por hoy y no puede "
             "enviarse a cocina. Se reactiva automaticamente cada dia.",
    )

    def action_kitchen_mark_unavailable(self):
        """Marca el plato como agotado por hoy (lo quita del menu del dia)."""
        self.write({"kitchen_available_today": False})
        for tmpl in self:
            if hasattr(tmpl, "message_post"):
                tmpl.message_post(
                    body=_("Plato marcado como AGOTADO por hoy. No se podra enviar a cocina hasta manana."),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

    def action_kitchen_mark_available(self):
        """Reactiva el plato manualmente."""
        self.write({"kitchen_available_today": True})

    @api.model
    def _cron_reset_kitchen_availability(self):
        """Reactiva todos los platos agotados al inicio de cada dia.

        Asi el 'agotado' aplica solo 'por ese dia', como pide el cliente.
        """
        sold_out = self.search([("kitchen_available_today", "=", False)])
        if sold_out:
            sold_out.write({"kitchen_available_today": True})
