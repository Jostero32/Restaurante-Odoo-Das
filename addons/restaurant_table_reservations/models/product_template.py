from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    available_for_reservation_preorder = fields.Boolean(
        string="Disponible para pre-orden de reserva",
        default=False,
        help="Si esta marcado, el cliente puede agregar este producto al pre-pedido cuando reserva una mesa.",
    )
    preorder_qty_follows_party_size = fields.Boolean(
        string="Cantidad por persona en pre-orden",
        default=False,
        help=(
            "Si esta marcado, al agregar este producto al pre-pedido la cantidad "
            "inicial se ajusta al numero de personas de la reserva (ej. 'Menu ejecutivo por persona'). "
            "El cliente puede sobrescribir la cantidad manualmente."
        ),
    )
