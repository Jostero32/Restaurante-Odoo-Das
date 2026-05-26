from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RestaurantDeliveryOrder(models.Model):
    _name = "restaurant.delivery.order"
    _description = "Pedido a domicilio"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "order_datetime desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default=lambda self: _("Nuevo pedido"),
        tracking=True,
    )
    customer_name = fields.Char(string="Cliente", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente (partner)",
        help="Enlace opcional al contacto del cliente (res.partner)",
        tracking=True,
    )
    customer_phone = fields.Char(string="Telefono", tracking=True)
    delivery_address = fields.Char(string="Direccion de entrega", required=True, tracking=True)
    order_datetime = fields.Datetime(
        string="Fecha del pedido",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    eta_minutes = fields.Integer(string="ETA minutos", default=35, tracking=True)
    estimated_delivery_datetime = fields.Datetime(
        string="Estimated delivery datetime",
        compute="_compute_estimated_delivery_datetime",
        store=True,
    )
    amount_total = fields.Monetary(string="Total", currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    delivery_user_id = fields.Many2one("res.users", string="Repartidor", tracking=True)
    driver_id = fields.Many2one(
        "res.users",
        string="Repartidor",
        related="delivery_user_id",
        readonly=False,
        store=False,
    )
    notes = fields.Text(string="Notas")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("assigned", "Asignado"),
            ("on_route", "En ruta"),
            ("delivered", "Entregado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.constrains("eta_minutes")
    def _check_eta_minutes(self):
        for order in self:
            if order.eta_minutes < 0:
                raise ValidationError(_("El ETA no puede ser negativo."))

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_assign(self):
        for order in self:
            if not order.driver_id:
                raise UserError(_("Asigne un repartidor antes de marcar el pedido como asignado."))
        self.write({"state": "assigned"})

    def action_on_route(self):
        self.write({"state": "on_route"})

    def action_delivered(self):
        self.write({"state": "delivered"})

    def action_cancel(self):
        delivered = self.filtered(lambda order: order.state == "delivered")
        if delivered:
            raise UserError(_("No puede cancelar un pedido entregado."))
        self.write({"state": "cancelled"})

    @api.depends('order_datetime', 'eta_minutes')
    def _compute_estimated_delivery_datetime(self):
        for order in self:
            if order.order_datetime and order.eta_minutes is not None:
                try:
                    # order_datetime is a datetime string in UTC-aware fields
                    order_dt = fields.Datetime.from_string(order.order_datetime)
                except Exception:
                    order.estimated_delivery_datetime = False
                    continue
                # add minutes
                from datetime import timedelta

                order.estimated_delivery_datetime = fields.Datetime.to_string(
                    order_dt + timedelta(minutes=order.eta_minutes)
                )
            else:
                order.estimated_delivery_datetime = False
