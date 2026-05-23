from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RestaurantDeliveryIncident(models.Model):
    _name = "restaurant.delivery.incident"
    _description = "Incidencia de pedido delivery"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "reported_datetime desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default=lambda self: _("Nueva incidencia"),
        tracking=True,
    )
    delivery_order_id = fields.Many2one(
        "restaurant.delivery.order",
        string="Pedido delivery",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido de venta",
        related="delivery_order_id.sale_order_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        tracking=True,
    )
    issue_type = fields.Selection(
        [
            ("incomplete", "Pedido incompleto"),
            ("cold", "Producto frio"),
            ("delay", "Demora"),
            ("wrong_item", "Producto incorrecto"),
            ("other", "Otro"),
        ],
        string="Tipo de incidencia",
        required=True,
        default="other",
        tracking=True,
    )
    description = fields.Text(string="Descripcion", required=True)
    state = fields.Selection(
        [
            ("new", "Nueva"),
            ("in_review", "En revision"),
            ("resolved", "Resuelta"),
            ("rejected", "No procede"),
        ],
        string="Estado",
        default="new",
        required=True,
        tracking=True,
    )
    resolution_notes = fields.Text(string="Notas de resolucion")
    reported_datetime = fields.Datetime(
        string="Fecha de reporte",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nueva incidencia"):
                vals["name"] = self.env["ir.sequence"].next_by_code("restaurant.delivery.incident") or _(
                    "Nueva incidencia"
                )
            if not vals.get("partner_id") and vals.get("delivery_order_id"):
                order = self.env["restaurant.delivery.order"].browse(vals["delivery_order_id"])
                vals["partner_id"] = order.partner_id.id
        incidents = super().create(vals_list)
        for incident in incidents:
            incident.delivery_order_id.message_post(
                body=_("Se reporto una incidencia (%s): %s", incident.issue_type, incident.description),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        return incidents

    @api.constrains("partner_id", "delivery_order_id")
    def _check_partner_matches_order(self):
        for incident in self:
            order_partner = incident.delivery_order_id.partner_id
            if not order_partner or not incident.partner_id:
                continue
            if incident.partner_id.commercial_partner_id != order_partner.commercial_partner_id:
                raise ValidationError(
                    _("El cliente de la incidencia debe pertenecer al mismo cliente comercial del pedido.")
                )

    def action_in_review(self):
        self.write({"state": "in_review"})

    def action_resolved(self):
        self.write({"state": "resolved"})

    def action_rejected(self):
        self.write({"state": "rejected"})
