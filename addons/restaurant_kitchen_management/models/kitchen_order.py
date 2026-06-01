from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        # Propagar el estado al pedido delivery (si aplica)
        for order in self:
            delivery = order.delivery_order_id
            if not delivery:
                continue
            if not delivery.kitchen_ready:
                delivery.sudo().write({"kitchen_ready": True})

            # Notificar SIEMPRE al(los) repartidor(es) responsables y dejar
            # un mensaje en el chatter del delivery con detalle accionable.
            driver = delivery.driver_id
            if driver:
                # Mensaje dirigido al repartidor asignado.
                delivery.sudo().message_post(
                    body=_(
                        "Cocina marco el pedido %(name)s como LISTO para despacho. "
                        "Repartidor asignado: %(driver)s."
                    ) % {"name": order.name, "driver": driver.name},
                    partner_ids=[driver.partner_id.id] if driver.partner_id else [],
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
                # Crear una actividad "todo" para el repartidor.
                todo_type = self.env.ref(
                    "mail.mail_activity_data_todo", raise_if_not_found=False
                )
                if todo_type:
                    self.env["mail.activity"].sudo().create({
                        "activity_type_id": todo_type.id,
                        "res_model_id": self.env["ir.model"]._get_id(
                            "restaurant.delivery.order"
                        ),
                        "res_id": delivery.id,
                        "user_id": driver.id,
                        "summary": _("Pedido listo para despacho"),
                        "note": _(
                            "El pedido %s ya esta listo en cocina. "
                            "Recogerlo y salir a entregar."
                        ) % delivery.name,
                        "date_deadline": fields.Date.context_today(self),
                    })
            else:
                # Sin repartidor: avisar a admin/administracion para asignar.
                delivery.sudo().message_post(
                    body=_(
                        "Cocina marco el pedido %s como LISTO. "
                        "Sin repartidor asignado: asigne uno para despachar."
                    ) % order.name,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

    def action_served(self):
        """Para POS = servida al cliente.
        Para Delivery = despachada al repartidor.
        """
        self.write({
            "state": "served",
            "served_at": fields.Datetime.now(),
        })

    def action_cancel(self):
        # Avisar al delivery si la orden cancelada provenia de uno: el
        # admin/repartidor necesita saber que cocina ya no va a preparar.
        for order in self:
            delivery = order.delivery_order_id
            if delivery and delivery.state not in ("delivered", "cancelled"):
                delivery.sudo().message_post(
                    body=_(
                        "Cocina cancelo la orden %s. "
                        "Revise el pedido antes de continuar el despacho."
                    ) % order.name,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
                # Si el delivery aun tenia kitchen_ready, lo desmarcamos.
                if delivery.kitchen_ready:
                    delivery.sudo().write({"kitchen_ready": False})
        self.write({"state": "cancelled"})

    # ------------------------------------------------------------------
    # API para el POS (RPC desde JavaScript / OWL)
    # ------------------------------------------------------------------
    @api.model
    def create_from_pos(self, pos_order_id, lines_data, context_data=None):
        """Crea una orden de cocina desde el POS.

        :param pos_order_id: ID de la pos.order (puede ser False si aun no se guardo)
        :param lines_data: lista de dicts con
            {product_id, quantity, line_note, source_pos_line_uuid}
        :param context_data: dict opcional con {table_id, partner_id, session_id}
            usado cuando la pos.order aun no se ha persistido en el backend.
        :return: dict con kitchen_order_id, name, line_count o warning.
        """
        context_data = context_data or {}
        if not lines_data:
            return {"warning": _("No hay productos para enviar a cocina.")}

        # Filtrar duplicados por UUID si ya existe una orden para esta pos.order
        existing = self.env["restaurant.kitchen.order"]
        if pos_order_id:
            existing = self.search([("pos_order_id", "=", pos_order_id)])
        existing_uuids = set(existing.mapped("line_ids.source_pos_line_uuid"))
        new_lines = [
            ld for ld in lines_data
            if not ld.get("source_pos_line_uuid")
            or ld["source_pos_line_uuid"] not in existing_uuids
        ]
        if not new_lines:
            return {"warning": _("Los productos ya fueron enviados a cocina.")}

        # Resolver mesa / cliente / sesion: primero del pos.order si existe,
        # si no del context_data enviado desde el POS frontend.
        pos_order = self.env["pos.order"].browse(pos_order_id) if pos_order_id else False
        table_id = False
        partner_id = False
        session_id = False
        if pos_order and pos_order.exists():
            table_id = pos_order.table_id.id if "table_id" in pos_order._fields and pos_order.table_id else False
            partner_id = pos_order.partner_id.id if pos_order.partner_id else False
            session_id = pos_order.session_id.id if pos_order.session_id else False
        table_id = table_id or context_data.get("table_id") or False
        partner_id = partner_id or context_data.get("partner_id") or False
        session_id = session_id or context_data.get("session_id") or False

        # Si ya existe una orden activa para esta pos.order, le sumamos lineas
        # en lugar de crear una nueva. Asi soportamos pedidos modificados.
        active = existing.filtered(lambda k: k.state in ("new", "preparing"))
        if active:
            target = active[:1]
            target.write({
                "line_ids": [(0, 0, ld) for ld in new_lines],
            })
            target.message_post(
                body=_("Se agregaron %s productos adicionales desde POS.") % len(new_lines),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            return {
                "kitchen_order_id": target.id,
                "name": target.name,
                "line_count": len(new_lines),
                "appended": True,
            }

        # Caso normal: crear orden nueva
        kitchen_order = self.create({
            "origin_type": "pos",
            "pos_order_id": pos_order.id if pos_order else False,
            "pos_session_id": session_id,
            "table_id": table_id,
            "partner_id": partner_id,
            "line_ids": [(0, 0, ld) for ld in new_lines],
        })
        return {
            "kitchen_order_id": kitchen_order.id,
            "name": kitchen_order.name,
            "line_count": len(new_lines),
            "appended": False,
        }

    @api.model
    def get_orders_for_pos(self, session_id=None, states=None):
        """Devuelve ordenes de cocina del origen POS para el frontend del POS.

        :param session_id: ID de la sesion POS para filtrar (opcional)
        :param states: lista de estados a incluir; default ['new','preparing','ready']
        :return: lista de dicts con resumen de cada orden.
        """
        states = states or ["new", "preparing", "ready"]
        domain = [("origin_type", "=", "pos"), ("state", "in", states)]
        if session_id:
            domain.append(("pos_session_id", "=", session_id))
        orders = self.search(domain, order="sent_at desc", limit=200)
        return [{
            "id": o.id,
            "name": o.name,
            "state": o.state,
            "table_id": o.table_id.id if o.table_id else False,
            "table_name": o.table_id.name if o.table_id else "",
            "pos_order_id": o.pos_order_id.id if o.pos_order_id else False,
            "sent_at": fields.Datetime.to_string(o.sent_at) if o.sent_at else False,
            "ready_at": fields.Datetime.to_string(o.ready_at) if o.ready_at else False,
            "line_count": len(o.line_ids),
            "products": [
                {
                    "name": l.product_id.display_name,
                    "qty": l.quantity,
                    "note": l.line_note or "",
                }
                for l in o.line_ids
            ],
        } for o in orders]

    def mark_served_from_pos(self):
        """Wrapper para llamar action_served desde el POS via RPC.

        Solo permitido para ordenes con origen POS o manual: las ordenes
        de delivery NO se sirven (se despachan al repartidor), por lo que
        deben cerrarse desde el backend con el boton "Marcar Despachada".
        """
        invalid = self.filtered(lambda o: o.origin_type == "delivery")
        if invalid:
            raise UserError(_(
                "No se puede marcar como servida una orden de delivery desde el POS. "
                "Use el boton 'Marcar Despachada' en el backend."
            ))
        self.action_served()
        return True
