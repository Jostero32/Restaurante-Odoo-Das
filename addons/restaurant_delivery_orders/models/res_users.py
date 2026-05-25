from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    delivery_rating_average = fields.Float(
        string="Calificacion promedio (delivery)",
        compute="_compute_delivery_rating_summary",
        help="Promedio de estrellas recibidas como repartidor en pedidos delivery.",
    )
    delivery_rating_count = fields.Integer(
        string="Total calificaciones (delivery)",
        compute="_compute_delivery_rating_summary",
    )

    @api.depends_context("uid")
    def _compute_delivery_rating_summary(self):
        Rating = self.env["restaurant.delivery.rating"].sudo()
        for user in self:
            ratings = Rating.search([("driver_id", "=", user.id)])
            if ratings:
                user.delivery_rating_count = len(ratings)
                user.delivery_rating_average = round(
                    sum(r.score_int for r in ratings) / len(ratings), 2
                )
            else:
                user.delivery_rating_count = 0
                user.delivery_rating_average = 0.0
