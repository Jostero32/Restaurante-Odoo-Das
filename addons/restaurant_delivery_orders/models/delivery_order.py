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
    amount_total = fields.Monetary(string="Total", currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    driver_id = fields.Many2one("res.users", string="Repartidor", tracking=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nuevo pedido"):
                vals["name"] = self.env["ir.sequence"].next_by_code("restaurant.delivery.order") or _("Nuevo pedido")
        return super().create(vals_list)

    @api.model
    def _disable_ecommerce_terms_block(self):
        terms_view = self.env["ir.ui.view"].sudo().search(
            [("key", "=", "website_sale.product_custom_text"), ("active", "=", True)],
            limit=1,
        )
        if terms_view:
            terms_view.write({"active": False})

    @api.model
    def _migrate_legacy_delivery_orders(self):
        self.env.cr.execute(
            """
            UPDATE restaurant_delivery_order
               SET state = 'on_route'
             WHERE state = 'on_the_way'
            """
        )
        self.env.cr.execute(
            """
            UPDATE restaurant_delivery_order
               SET customer_name = 'Cliente no especificado'
             WHERE customer_name IS NULL OR btrim(customer_name) = ''
            """
        )

    @api.constrains("eta_minutes")
    def _check_eta_minutes(self):
        for order in self:
            if order.eta_minutes < 0:
                raise ValidationError(_("El ETA no puede ser negativo."))

    def action_confirm(self):
        invalid = self.filtered(lambda order: order.state != "draft")
        if invalid:
            raise UserError(_("Solo se pueden confirmar pedidos en borrador."))
        self.write({"state": "confirmed"})

    def action_assign(self):
        invalid = self.filtered(lambda order: order.state != "confirmed")
        if invalid:
            raise UserError(_("Solo se pueden asignar pedidos confirmados."))
        for order in self:
            if not order.driver_id:
                raise UserError(_("Asigne un repartidor antes de marcar el pedido como asignado."))
        self.write({"state": "assigned"})

    def action_on_route(self):
        invalid = self.filtered(lambda order: order.state != "assigned")
        if invalid:
            raise UserError(_("Solo se pueden pasar a en ruta pedidos asignados."))
        without_driver = self.filtered(lambda order: not order.driver_id)
        if without_driver:
            raise UserError(_("No se puede poner en ruta un pedido sin repartidor asignado."))
        self.write({"state": "on_route"})

    def action_delivered(self):
        invalid = self.filtered(lambda order: order.state != "on_route")
        if invalid:
            raise UserError(_("Solo se pueden entregar pedidos en ruta."))
        self.write({"state": "delivered"})

    def action_cancel(self):
        delivered = self.filtered(lambda order: order.state == "delivered")
        if delivered:
            raise UserError(_("No puede cancelar un pedido entregado."))
        self.write({"state": "cancelled"})
