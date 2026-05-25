from odoo import _, api, fields, models


class RestaurantKitchenOrder(models.Model):
    _name = "restaurant.kitchen.order"
    _description = "Orden de Cocina"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sent_at desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default="New",
        tracking=True,
    )
    origin_type = fields.Selection(
        [
            ("pos", "Punto de Venta"),
            ("delivery", "Delivery"),
            ("manual", "Manual"),
        ],
        string="Origen",
        required=True,
        default="manual",
        tracking=True,
    )
    pos_order_id = fields.Many2one(
        "pos.order",
        string="Orden POS",
        copy=False,
        tracking=True,
    )
    delivery_order_id = fields.Many2one(
        "restaurant.delivery.order",
        string="Pedido Delivery",
        copy=False,
        tracking=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido de Venta",
        copy=False,
        tracking=True,
    )
    table_id = fields.Many2one(
        "restaurant.table",
        string="Mesa",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        tracking=True,
    )
    waiter_user_id = fields.Many2one(
        "res.users",
        string="Mesero / Usuario",
        default=lambda self: self.env.user,
        tracking=True,
    )
    pos_session_id = fields.Many2one(
        "pos.session",
        string="Sesion POS",
        copy=False,
    )
    state = fields.Selection(
        [
            ("new", "Nueva"),
            ("preparing", "En Preparacion"),
            ("ready", "Lista"),
            ("served", "Servida"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="new",
        required=True,
        tracking=True,
    )
    sent_at = fields.Datetime(
        string="Enviada a cocina",
        copy=False,
    )
    started_at = fields.Datetime(
        string="Inicio preparacion",
        copy=False,
    )
    ready_at = fields.Datetime(
        string="Lista",
        copy=False,
    )
    served_at = fields.Datetime(
        string="Servida",
        copy=False,
    )
    notes = fields.Text(string="Notas")
    line_ids = fields.One2many(
        "restaurant.kitchen.order.line",
        "kitchen_order_id",
        string="Lineas",
    )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("restaurant.kitchen.order")
                    or _("New")
                )
            if not vals.get("sent_at"):
                vals["sent_at"] = fields.Datetime.now()
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # State actions
    # ------------------------------------------------------------------
    def action_start(self):
        self.write({
            "state": "preparing",
            "started_at": fields.Datetime.now(),
        })

    def action_ready(self):
        self.write({
            "state": "ready",
            "ready_at": fields.Datetime.now(),
        })

    def action_served(self):
        self.write({
            "state": "served",
            "served_at": fields.Datetime.now(),
        })

    def action_cancel(self):
        self.write({"state": "cancelled"})
