from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


SCORE_SELECTION = [
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
    ("5", "5"),
]


class RestaurantDeliveryRating(models.Model):
    _name = "restaurant.delivery.rating"
    _description = "Calificacion de pedido delivery"
    _order = "rated_at desc, id desc"

    delivery_order_id = fields.Many2one(
        "restaurant.delivery.order",
        string="Pedido delivery",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
    )
    driver_id = fields.Many2one(
        "res.users",
        string="Repartidor",
        help="Repartidor que entrego el pedido en el momento de la calificacion.",
    )
    score = fields.Selection(
        SCORE_SELECTION,
        string="Estrellas",
        required=True,
    )
    score_int = fields.Integer(
        string="Puntaje",
        compute="_compute_score_int",
        store=True,
        help="Version entera del puntaje para promedios.",
    )
    comment = fields.Text(string="Comentario")
    rated_at = fields.Datetime(
        string="Fecha de calificacion",
        default=fields.Datetime.now,
        required=True,
    )

    _sql_constraints = [
        (
            "rating_per_order_unique",
            "unique(delivery_order_id)",
            "Este pedido ya tiene una calificacion registrada.",
        ),
    ]

    @api.depends("score")
    def _compute_score_int(self):
        for rating in self:
            try:
                rating.score_int = int(rating.score) if rating.score else 0
            except (TypeError, ValueError):
                rating.score_int = 0

    @api.constrains("delivery_order_id")
    def _check_order_delivered(self):
        for rating in self:
            if rating.delivery_order_id.state != "delivered":
                raise ValidationError(
                    _("Solo se puede calificar un pedido entregado.")
                )
