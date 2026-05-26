from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RestaurantKitchenOrder(models.Model):
    _name = "restaurant.kitchen.order"
    _description = "Orden de Cocina"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sent_at desc, id desc"

    # ─── Identificación ──────────────────────────────────────────────────────

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nueva orden"),
        tracking=True,
    )

    # ─── Origen de la orden ──────────────────────────────────────────────────

    origin_type = fields.Selection(
        selection=[
            ("pos", "Punto de Venta (POS)"),
            ("delivery", "Delivery"),
            ("manual", "Manual"),
        ],
        string="Origen",
        required=True,
        default="manual",
        tracking=True,
    )

    # Referencia al pedido POS (almacenada como texto para no depender del
    # módulo point_of_sale en este momento).
    pos_order_id = fields.Char(
        string="Referencia POS",
        copy=False,
        help="Identificador del pedido en el Punto de Venta (POS). "
             "Se completará automáticamente al integrar con el módulo POS.",
    )
    pos_session_id = fields.Char(
        string="Sesión POS",
        copy=False,
        help="Identificador de la sesión POS asociada. "
             "Se completará automáticamente al integrar con el módulo POS.",
    )

    # Referencia al pedido de delivery
    delivery_order_id = fields.Many2one(
        comodel_name="restaurant.delivery.order",
        string="Pedido Delivery",
        ondelete="set null",
        copy=False,
        tracking=True,
    )

    # ─── Relaciones con mesa, cliente y mesero ────────────────────────────────

    table_id = fields.Many2one(
        comodel_name="restaurant.table",
        string="Mesa",
        ondelete="set null",
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        ondelete="set null",
        tracking=True,
    )
    waiter_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Mesero",
        ondelete="set null",
        default=lambda self: self.env.user,
        tracking=True,
    )

    # ─── Estado ──────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ("new", "Nueva"),
            ("preparing", "En preparación"),
            ("ready", "Lista"),
            ("served", "Servida"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="new",
        required=True,
        copy=False,
        tracking=True,
    )

    # ─── Trazabilidad de tiempos ──────────────────────────────────────────────

    sent_at = fields.Datetime(
        string="Enviada a cocina",
        default=fields.Datetime.now,
        copy=False,
        readonly=True,
    )
    started_at = fields.Datetime(
        string="Inicio de preparación",
        copy=False,
        readonly=True,
    )
    ready_at = fields.Datetime(
        string="Lista a las",
        copy=False,
        readonly=True,
    )
    served_at = fields.Datetime(
        string="Servida a las",
        copy=False,
        readonly=True,
    )

    # ─── Notas y líneas ──────────────────────────────────────────────────────

    notes = fields.Text(string="Notas generales")

    line_ids = fields.One2many(
        comodel_name="restaurant.kitchen.order.line",
        inverse_name="kitchen_order_id",
        string="Líneas de la orden",
        copy=True,
    )

    # ─── Campos calculados ────────────────────────────────────────────────────

    line_count = fields.Integer(
        string="Nº de ítems",
        compute="_compute_line_count",
        store=True,
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for order in self:
            order.line_count = len(order.line_ids)

    # ─── Secuencia ────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nueva orden")) == _("Nueva orden"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "restaurant.kitchen.order"
                ) or _("Nueva orden")
        return super().create(vals_list)

    # ─── Transiciones de estado ───────────────────────────────────────────────

    def action_start_preparing(self):
        """Confirma que cocina comenzó a preparar la orden."""
        for order in self:
            if order.state != "new":
                raise UserError(
                    _("Solo se pueden empezar a preparar órdenes en estado 'Nueva'.")
                )
            order.write({
                "state": "preparing",
                "started_at": fields.Datetime.now(),
            })
            order._update_lines_state("preparing")

    def action_mark_ready(self):
        """Marca la orden como lista para ser servida."""
        for order in self:
            if order.state != "preparing":
                raise UserError(
                    _("Solo se pueden marcar como listas las órdenes 'En preparación'.")
                )
            order.write({
                "state": "ready",
                "ready_at": fields.Datetime.now(),
            })
            order._update_lines_state("done")

    def action_mark_served(self):
        """Registra que la orden fue entregada al cliente."""
        for order in self:
            if order.state not in ("ready", "preparing"):
                raise UserError(
                    _("Solo se pueden servir órdenes listas o en preparación.")
                )
            order.write({
                "state": "served",
                "served_at": fields.Datetime.now(),
            })

    def action_cancel(self):
        """Cancela la orden. No se puede cancelar si ya fue servida."""
        for order in self:
            if order.state == "served":
                raise UserError(
                    _("No se puede cancelar una orden que ya fue servida.")
                )
            order.write({"state": "cancelled"})
            order._update_lines_state("cancelled")

    def action_reset_to_new(self):
        """Devuelve la orden a estado 'Nueva' (solo desde cancelada)."""
        for order in self:
            if order.state != "cancelled":
                raise UserError(
                    _("Solo se pueden reactivar órdenes canceladas.")
                )
            order.write({
                "state": "new",
                "started_at": False,
                "ready_at": False,
                "served_at": False,
            })
            order._update_lines_state("pending")

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _update_lines_state(self, new_state):
        """Actualiza el estado de todas las líneas de la orden."""
        valid_line_states = ["pending", "preparing", "done", "cancelled"]
        if new_state in valid_line_states:
            self.line_ids.write({"state": new_state})

    # ─── Nombre display ───────────────────────────────────────────────────────

    def name_get(self):
        result = []
        for order in self:
            name = order.name
            if order.table_id:
                name = f"{name} [{order.table_id.name}]"
            result.append((order.id, name))
        return result
