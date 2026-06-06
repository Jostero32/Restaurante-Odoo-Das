from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class RestaurantDeliveryOrder(models.Model):
    _name = "restaurant.delivery.order"
    _description = "Pedido a domicilio"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
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
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    notes = fields.Text(string="Notas")
    state = fields.Selection(
        [
            ("draft", "Recibido"),
            ("confirmed", "En preparacion"),
            ("assigned", "Asignado"),
            ("on_route", "En camino"),
            ("delivered", "Entregado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido de venta",
        copy=False,
        tracking=True,
        ondelete="set null",
    )
    is_scheduled = fields.Boolean(
        string="Programado",
        default=False,
        copy=False,
        tracking=True,
        help="Indica si el cliente eligio una hora especifica de entrega.",
    )
    scheduled_for = fields.Datetime(
        string="Programado para",
        copy=False,
        tracking=True,
        help="Hora especifica solicitada por el cliente para la entrega.",
    )
    product_summary = fields.Text(string="Productos del pedido", compute="_compute_product_summary")
    linked_invoice_ids = fields.Many2many(
        "account.move",
        string="Facturas relacionadas",
        compute="_compute_invoice_metrics",
        readonly=True,
    )
    invoice_count = fields.Integer(string="Facturas", compute="_compute_invoice_metrics")
    invoice_paid_count = fields.Integer(string="Facturas pagadas", compute="_compute_invoice_metrics")
    invoice_pending_count = fields.Integer(string="Facturas pendientes", compute="_compute_invoice_metrics")
    invoice_residual_amount = fields.Monetary(
        string="Saldo pendiente",
        compute="_compute_invoice_metrics",
        currency_field="currency_id",
    )

    incident_ids = fields.One2many(
        "restaurant.delivery.incident",
        "delivery_order_id",
        string="Incidencias",
    )
    customer_rating_ids = fields.One2many(
        "restaurant.delivery.rating",
        "delivery_order_id",
        string="Calificacion",
    )
    rating_score = fields.Integer(
        string="Calificacion (estrellas)",
        compute="_compute_rating_summary",
        store=True,
    )
    rating_comment = fields.Text(
        string="Comentario del cliente",
        compute="_compute_rating_summary",
        store=True,
    )
    has_rating = fields.Boolean(
        string="Tiene calificacion",
        compute="_compute_rating_summary",
        store=True,
    )
    incident_count = fields.Integer(string="Total incidencias", compute="_compute_incident_count")
    customer_status_label = fields.Char(string="Estado para cliente", compute="_compute_customer_status_label")
    display_state_key = fields.Char(
        string="Estado visual",
        compute="_compute_display_state",
        help="Estado visible para cliente y operativo. Distingue pedidos programados aun no en preparacion.",
    )
    scheduled_for_display = fields.Char(
        string="Programado para (texto)",
        compute="_compute_scheduled_for_display",
    )
    scheduled_lead_minutes = fields.Integer(
        string="Minutos hasta la entrega programada",
        compute="_compute_scheduled_for_display",
    )

    @api.model
    def _driver_domain(self):
        repartidor_group = self.env.ref(
            "restaurant_casa_vieja_base.group_restaurant_repartidor", raise_if_not_found=False
        )
        administrador_group = self.env.ref(
            "restaurant_casa_vieja_base.group_restaurant_administrador", raise_if_not_found=False
        )
        domain = [("share", "=", False)]
        if repartidor_group:
            domain.append(("groups_id", "in", [repartidor_group.id]))
        if administrador_group:
            domain.append(("groups_id", "not in", [administrador_group.id]))
        return domain

    driver_id = fields.Many2one(
        "res.users",
        string="Repartidor",
        tracking=True,
        domain=lambda self: self._driver_domain(),
    )

    @api.depends("incident_ids")
    def _compute_incident_count(self):
        for order in self:
            order.incident_count = len(order.incident_ids)

    @api.depends("customer_rating_ids.score_int", "customer_rating_ids.comment")
    def _compute_rating_summary(self):
        for order in self:
            rating = order.customer_rating_ids[:1]
            order.has_rating = bool(rating)
            order.rating_score = rating.score_int if rating else 0
            order.rating_comment = rating.comment if rating else ""

    @api.depends(
        "sale_order_id",
        "sale_order_id.order_line",
        "sale_order_id.order_line.display_type",
        "sale_order_id.order_line.name",
        "sale_order_id.order_line.product_uom_qty",
        "sale_order_id.order_line.product_uom",
    )
    def _compute_product_summary(self):
        for order in self:
            lines = order.sale_order_id.sudo().order_line.filtered(lambda line: not line.display_type)
            if not lines:
                order.product_summary = ""
                continue
            chunks = []
            for line in lines:
                uom_name = line.product_uom.name if line.product_uom else ""
                if uom_name:
                    chunks.append(f"- {line.name} x {line.product_uom_qty:g} {uom_name}")
                else:
                    chunks.append(f"- {line.name} x {line.product_uom_qty:g}")
            order.product_summary = "\n".join(chunks)

    @api.depends(
        "sale_order_id",
        "sale_order_id.invoice_ids",
        "sale_order_id.invoice_ids.move_type",
        "sale_order_id.invoice_ids.state",
        "sale_order_id.invoice_ids.payment_state",
        "sale_order_id.invoice_ids.amount_residual",
    )
    def _compute_invoice_metrics(self):
        customer_invoice_types = {"out_invoice", "out_refund", "out_receipt"}
        for order in self:
            invoices = order.sale_order_id.sudo().invoice_ids.filtered(
                lambda inv: inv.move_type in customer_invoice_types and inv.state != "cancel"
            )
            posted_invoices = invoices.filtered(lambda inv: inv.state == "posted")
            pending_invoices = posted_invoices.filtered(
                lambda inv: inv.payment_state not in {"paid", "reversed"}
            )
            paid_invoices = posted_invoices.filtered(
                lambda inv: inv.payment_state in {"paid", "reversed"}
            )

            order.linked_invoice_ids = invoices
            order.invoice_count = len(invoices)
            order.invoice_pending_count = len(pending_invoices)
            order.invoice_paid_count = len(paid_invoices)
            order.invoice_residual_amount = sum(posted_invoices.mapped("amount_residual")) if posted_invoices else 0.0

    _PREP_LEAD_MINUTES = 90  # umbral para distinguir "programado" de "en preparacion"

    def _get_customer_state_label(self, state_value=None, display_key=None):
        # Si tenemos display_key explicito (p.ej. scheduled_received), prevalece.
        scheduled_mapping = {
            "scheduled_received": _("Pedido recibido"),
        }
        if display_key in scheduled_mapping:
            return scheduled_mapping[display_key]
        mapping = {
            "draft": _("En preparacion"),
            "confirmed": _("En preparacion"),
            "assigned": _("En preparacion"),
            "on_route": _("En camino"),
            "delivered": _("Entregado"),
            "cancelled": _("Cancelado"),
        }
        return mapping.get(state_value or self.state, _("En proceso"))

    @api.depends("state", "is_scheduled", "scheduled_for")
    def _compute_display_state(self):
        now = fields.Datetime.now()
        for order in self:
            order.display_state_key = order._resolve_display_state_key(now)

    def _resolve_display_state_key(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        if self.state in {"on_route", "delivered", "cancelled"}:
            return self.state
        if self.is_scheduled and self.scheduled_for and self.state in {"draft", "confirmed"}:
            delta = (self.scheduled_for - now).total_seconds() / 60.0
            if delta > self._PREP_LEAD_MINUTES:
                return "scheduled_received"
        return self.state

    @api.depends("state", "is_scheduled", "scheduled_for", "display_state_key")
    def _compute_customer_status_label(self):
        for order in self:
            order.customer_status_label = order._get_customer_state_label(
                order.state, display_key=order.display_state_key
            )

    @api.depends("is_scheduled", "scheduled_for")
    def _compute_scheduled_for_display(self):
        now = fields.Datetime.now()
        for order in self:
            if not order.is_scheduled or not order.scheduled_for:
                order.scheduled_for_display = ""
                order.scheduled_lead_minutes = 0
                continue
            delta_seconds = (order.scheduled_for - now).total_seconds()
            order.scheduled_lead_minutes = int(delta_seconds / 60)
            order.scheduled_for_display = order._format_scheduled_for(now)

    def _format_scheduled_for(self, now=None):
        self.ensure_one()
        if not self.scheduled_for:
            return ""
        now = now or fields.Datetime.now()
        schedule = self.env["restaurant.delivery.schedule"].sudo()._get_or_create_for_company(self.company_id)
        local_when = schedule._to_company_local(self.scheduled_for)
        local_now = schedule._to_company_local(now)
        delta_days = (local_when.date() - local_now.date()).days
        time_part = local_when.strftime("%H:%M")
        if delta_days == 0:
            day_part = _("hoy")
        elif delta_days == 1:
            day_part = _("manana")
        elif 1 < delta_days <= 6:
            day_names = [
                _("lunes"), _("martes"), _("miercoles"), _("jueves"),
                _("viernes"), _("sabado"), _("domingo"),
            ]
            day_part = _("%(day)s (en %(n)s dias)") % {
                "day": day_names[local_when.weekday()],
                "n": delta_days,
            }
        elif delta_days < 0:
            day_part = local_when.strftime("%d/%m")
        else:
            day_part = local_when.strftime("%d/%m")
        return _("%(day)s a las %(time)s") % {"day": day_part, "time": time_part}

    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = f"/my/delivery/{order.id}"

    @api.model
    def _is_repartidor_only_user(self):
        user = self.env.user
        return (
            user.has_group("restaurant_casa_vieja_base.group_restaurant_repartidor")
            and not user.has_group("restaurant_casa_vieja_base.group_restaurant_administracion")
            and not user.has_group("restaurant_casa_vieja_base.group_restaurant_administrador")
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_repartidor_only_user():
            raise AccessError(_("No tiene permisos para crear pedidos delivery."))
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nuevo pedido"):
                vals["name"] = self.env["ir.sequence"].next_by_code("restaurant.delivery.order") or _(
                    "Nuevo pedido"
                )
        orders = super().create(vals_list)
        orders._sync_chat_followers()
        if not self.env.context.get("skip_delivery_customer_notify"):
            orders._notify_customer_status_change(force_states={"confirmed", "assigned", "on_route"})
        if not self.env.context.get("skip_delivery_internal_notify"):
            orders._notify_internal_new_website_order()
        return orders

    def _sync_chat_followers(self, previous_driver_by_order=None):
        previous_driver_by_order = previous_driver_by_order or {}
        for order in self:
            partner_ids_to_add = []
            customer_partner = order.partner_id and order.partner_id.commercial_partner_id
            if customer_partner and customer_partner not in order.message_partner_ids:
                partner_ids_to_add.append(customer_partner.id)
            if order.driver_id and order.driver_id.partner_id:
                if order.driver_id.partner_id not in order.message_partner_ids:
                    partner_ids_to_add.append(order.driver_id.partner_id.id)
            if partner_ids_to_add:
                order.sudo().message_subscribe(partner_ids=list(set(partner_ids_to_add)))
            previous_driver = previous_driver_by_order.get(order.id)
            if previous_driver and order.driver_id and previous_driver != order.driver_id:
                stale_partner = previous_driver.partner_id
                if stale_partner and stale_partner != customer_partner:
                    order.sudo().message_unsubscribe(partner_ids=[stale_partner.id])

    def _notify_internal_new_website_order(self):
        """Al recibir un pedido web, notifica SOLO a quienes deben asignar
        repartidor (cocina + administracion + administrador). Los repartidores
        no se notifican aqui: recibiran su actividad cuando se les asigne
        especificamente el pedido (ver action_assign / _notify_driver_assigned).
        """
        website_orders = self.filtered(lambda order: order.sale_order_id and order.sale_order_id.website_id)
        if not website_orders:
            return

        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo_type:
            return

        users = self.env["res.users"]
        for group_xmlid in [
            "restaurant_casa_vieja_base.group_restaurant_cocinero",
            "restaurant_casa_vieja_base.group_restaurant_mesero",
            "restaurant_casa_vieja_base.group_restaurant_repartidor",
            "restaurant_casa_vieja_base.group_restaurant_administracion",
            "restaurant_casa_vieja_base.group_restaurant_administrador",
        ]:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                users |= group.sudo().users.filtered(lambda user: user.active and not user.share)
        if not users:
            return

        model_id = self.env["ir.model"]._get_id("restaurant.delivery.order")
        today = fields.Date.context_today(self)
        activity_vals = []
        for order in website_orders:
            display_key = order._resolve_display_state_key()
            if display_key == "scheduled_received":
                schedule_text = order.scheduled_for_display or ""
                order.sudo().message_post(
                    body=_(
                        "Nuevo pedido web PROGRAMADO para %s. "
                        "El alistamiento se programa para el dia de la entrega."
                    ) % (schedule_text,),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
                deadline = fields.Date.to_date(order.scheduled_for) if order.scheduled_for else today
                summary = _("Pedido programado para %s") % (schedule_text,)
                note = _(
                    "Pedido %(name)s programado por el cliente para %(when)s. "
                    "Alistar a tiempo para esa hora."
                ) % {"name": order.name, "when": schedule_text}
            else:
                order.sudo().message_post(
                    body=_(
                        "Nuevo pedido web confirmado. Estado operativo: En preparacion. "
                        "Revisar alistamiento y asignacion de ruta."
                    ),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
                deadline = today
                summary = _("Nuevo pedido web en preparacion")
                note = _("Pedido %s listo para alistar y despachar.") % (order.name,)
            for user in users:
                activity_vals.append(
                    {
                        "activity_type_id": todo_type.id,
                        "res_model_id": model_id,
                        "res_id": order.id,
                        "user_id": user.id,
                        "summary": summary,
                        "note": note,
                        "date_deadline": deadline,
                    }
                )
        if activity_vals:
            self.env["mail.activity"].sudo().create(activity_vals)

    def _notify_driver_assigned(self, previous_driver_id=None):
        """Notifica al repartidor recien asignado y limpia actividades viejas
        de otros repartidores sobre este mismo pedido. Asi solo el repartidor
        actual ve la tarea pendiente.
        """
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        repartidor_group = self.env.ref(
            "restaurant_casa_vieja_base.group_restaurant_repartidor", raise_if_not_found=False
        )
        if not todo_type or not repartidor_group:
            return

        model_id = self.env["ir.model"]._get_id("restaurant.delivery.order")
        deadline = fields.Date.context_today(self)
        repartidor_user_ids = repartidor_group.sudo().users.ids

        for order in self:
            if not order.driver_id:
                continue

            # 1) Limpiar actividades viejas dirigidas a otros repartidores
            old_activities = self.env["mail.activity"].sudo().search([
                ("res_model", "=", "restaurant.delivery.order"),
                ("res_id", "=", order.id),
                ("user_id", "in", repartidor_user_ids),
                ("user_id", "!=", order.driver_id.id),
            ])
            if old_activities:
                old_activities.unlink()

            # 2) Crear actividad para el repartidor asignado
            existing = self.env["mail.activity"].sudo().search([
                ("res_model", "=", "restaurant.delivery.order"),
                ("res_id", "=", order.id),
                ("user_id", "=", order.driver_id.id),
                ("activity_type_id", "=", todo_type.id),
            ], limit=1)
            if not existing:
                self.env["mail.activity"].sudo().create({
                    "activity_type_id": todo_type.id,
                    "res_model_id": model_id,
                    "res_id": order.id,
                    "user_id": order.driver_id.id,
                    "summary": _("Pedido asignado para entrega"),
                    "note": _(
                        "Se te asigno el pedido %s. Coordinar recogida con cocina y entregar."
                    ) % order.name,
                    "date_deadline": deadline,
                })

            # 3) Mensaje en chatter dirigido al repartidor asignado
            partner_ids = [order.driver_id.partner_id.id] if order.driver_id.partner_id else []
            order.sudo().message_post(
                body=_(
                    "Pedido asignado al repartidor: %s."
                ) % order.driver_id.name,
                partner_ids=partner_ids,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    def write(self, vals):
        previous_states = {order.id: order.state for order in self}
        previous_drivers = {order.id: order.driver_id for order in self}
        previous_partners = {order.id: order.partner_id for order in self}
        if self._is_repartidor_only_user():
            allowed_fields = {"state", "notes"}
            forbidden_fields = set(vals) - allowed_fields
            if forbidden_fields:
                raise AccessError(
                    _("Como repartidor solo puede actualizar el estado y notas operativas del pedido.")
                )
            if "state" in vals and vals["state"] not in {"on_route", "delivered"}:
                raise AccessError(_("Como repartidor solo puede cambiar el estado a En camino o Entregado."))
        result = super().write(vals)
        if "state" in vals:
            changed = self.filtered(lambda order: previous_states.get(order.id) != order.state)
            changed._notify_customer_status_change()
        followers_changed = self.filtered(
            lambda order: previous_drivers.get(order.id) != order.driver_id
            or previous_partners.get(order.id) != order.partner_id
        )
        if followers_changed:
            followers_changed._sync_chat_followers(previous_driver_by_order=previous_drivers)
        # Si cambio el repartidor asignado: notificar al nuevo y limpiar viejos.
        if "driver_id" in vals:
            driver_changed = self.filtered(
                lambda o: previous_drivers.get(o.id) != o.driver_id and o.driver_id
            )
            if driver_changed:
                driver_changed._notify_driver_assigned()
        return result

    def unlink(self):
        if self._is_repartidor_only_user():
            raise AccessError(_("No tiene permisos para eliminar pedidos delivery."))
        return super().unlink()

    def _notify_customer_status_change(self, force_states=None):
        force_states = force_states or set()
        template = self.env.ref(
            "restaurant_delivery_orders.mail_template_delivery_status_update", raise_if_not_found=False
        )
        for order in self:
            if order.state not in {"confirmed", "assigned", "on_route", "delivered", "cancelled"} and order.state not in force_states:
                continue
            partner = order.partner_id or order.sale_order_id.partner_id
            if partner and partner.email:
                email_values = {"email_to": partner.email}
                if template:
                    template.sudo().send_mail(order.id, force_send=False, email_values=email_values)
            customer_label = order._get_customer_state_label(order.state, display_key=order.display_state_key)
            public_body = order._customer_chat_message_for_state(customer_label)
            if public_body:
                order.sudo().message_post(
                    body=public_body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            order.message_post(
                body=_("Actualizacion de estado enviada al cliente: %s") % (customer_label,),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def _customer_chat_message_for_state(self, customer_label):
        self.ensure_one()
        if self.state == "on_route":
            if self.driver_id:
                return _("Tu pedido va en camino con %s (repartidor). Coordina con el desde este chat si necesitas algo.") % (
                    self.driver_id.name,
                )
            return _("Tu pedido va en camino.")
        if self.state == "delivered":
            return _(
                "Tu pedido fue entregado. Gracias por preferirnos! "
                "Si quieres, calificalo desde la seccion de calificacion en esta misma pagina."
            )
        if self.state == "cancelled":
            return _("Tu pedido fue cancelado. Si tienes dudas, escribenos por este chat.")
        if self.state == "assigned":
            if self.driver_id:
                return _("Asignamos a %s como repartidor. Esta saliendo en breve.") % (self.driver_id.name,)
            return _("Asignamos un repartidor para tu pedido.")
        if self.display_state_key == "scheduled_received":
            return _("Recibimos tu pedido programado para %s. Te avisamos cuando inicie la preparacion.") % (
                self.scheduled_for_display,
            )
        if self.state == "confirmed":
            return _("Confirmamos tu pedido. Lo estamos preparando.")
        return ""

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

    @api.model
    def _cleanup_admin_repartidor_membership(self):
        admin_group = self.env.ref("restaurant_casa_vieja_base.group_restaurant_administrador", raise_if_not_found=False)
        repartidor_group = self.env.ref("restaurant_casa_vieja_base.group_restaurant_repartidor", raise_if_not_found=False)
        if not admin_group or not repartidor_group:
            return
        users_in_both = admin_group.users & repartidor_group.users
        if users_in_both:
            users_in_both.write({"groups_id": [(3, repartidor_group.id)]})

    @api.model
    def _enforce_single_address_storefront(self):
        # Storefront de delivery usa una sola direccion. El XML de seguridad
        # ya quita el grupo 'Delivery Address' de public/portal a futuro,
        # pero los usuarios existentes lo retienen por el many2many users.
        # Aqui los limpiamos, preservando internal users (backend).
        delivery_addr_group = self.env.ref(
            "account.group_delivery_invoice_address", raise_if_not_found=False
        )
        if not delivery_addr_group:
            return
        public_group = self.env.ref("base.group_public", raise_if_not_found=False)
        portal_group = self.env.ref("base.group_portal", raise_if_not_found=False)
        internal_group = self.env.ref("base.group_user", raise_if_not_found=False)
        if not internal_group or not (public_group or portal_group):
            return
        candidate_users = self.env["res.users"]
        if public_group:
            candidate_users |= public_group.sudo().users
        if portal_group:
            candidate_users |= portal_group.sudo().users
        candidate_users -= internal_group.sudo().users
        users_to_clean = candidate_users & delivery_addr_group.sudo().users
        if users_to_clean:
            delivery_addr_group.sudo().write(
                {"users": [(3, user.id) for user in users_to_clean]}
            )

    @api.model
    def _update_menu_groups(self, menu_xmlid, add_group_xmlids=None, remove_group_xmlids=None, replace_group_xmlids=None):
        menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
        if not menu:
            return

        if replace_group_xmlids is not None:
            group_ids = []
            for group_xmlid in replace_group_xmlids:
                group = self.env.ref(group_xmlid, raise_if_not_found=False)
                if group:
                    group_ids.append(group.id)
            menu.write({"groups_id": [(6, 0, group_ids)]})
            return

        commands = []
        for group_xmlid in remove_group_xmlids or []:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group and group in menu.groups_id:
                commands.append((3, group.id))
        for group_xmlid in add_group_xmlids or []:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group and group not in menu.groups_id:
                commands.append((4, group.id))
        if commands:
            menu.write({"groups_id": commands})

    @api.model
    def _lockdown_repartidor_backend_menus(self):
        # Repartidor mantiene acceso al backend, pero solo debe operar su flujo de delivery.
        allowed_non_driver_groups = [
            "restaurant_casa_vieja_base.group_restaurant_cocinero",
            "restaurant_casa_vieja_base.group_restaurant_mesero",
            "restaurant_casa_vieja_base.group_restaurant_administracion",
            "restaurant_casa_vieja_base.group_restaurant_administrador",
        ]
        menus_bound_to_internal_user = [
            "mail.menu_root_discuss",
            "calendar.mail_menu_calendar",
            "contacts.menu_contacts",
            "website.menu_website_configuration",
        ]
        for menu_xmlid in menus_bound_to_internal_user:
            self._update_menu_groups(
                menu_xmlid,
                add_group_xmlids=allowed_non_driver_groups,
                remove_group_xmlids=["base.group_user"],
            )

        # Menu de tableros suele venir sin grupos: se fuerza a roles no repartidor.
        self._update_menu_groups(
            "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
            replace_group_xmlids=allowed_non_driver_groups,
        )

        # Nodo secundario de website que puede quedar visible si existe.
        self._update_menu_groups(
            "website.menu_site",
            replace_group_xmlids=allowed_non_driver_groups,
        )

    @api.constrains("eta_minutes")
    def _check_eta_minutes(self):
        for order in self:
            if order.eta_minutes < 0:
                raise ValidationError(_("El ETA no puede ser negativo."))

    @api.constrains("is_scheduled", "scheduled_for")
    def _check_scheduled_for(self):
        for order in self:
            if order.is_scheduled and not order.scheduled_for:
                raise ValidationError(_("Marco el pedido como programado pero no indico hora."))
            if order.scheduled_for and not order.is_scheduled:
                # Tolerar pedidos historicos sin la bandera, no levantar.
                continue

    @api.constrains("driver_id")
    def _check_driver_role(self):
        repartidor_group = self.env.ref("restaurant_casa_vieja_base.group_restaurant_repartidor", raise_if_not_found=False)
        administrador_group = self.env.ref("restaurant_casa_vieja_base.group_restaurant_administrador", raise_if_not_found=False)
        for order in self:
            driver = order.driver_id
            if not driver:
                continue
            if repartidor_group and repartidor_group not in driver.groups_id:
                raise ValidationError(_("El usuario asignado no pertenece al rol Repartidor Restaurante."))
            if administrador_group and administrador_group in driver.groups_id:
                raise ValidationError(_("No se puede asignar un Administrador Restaurante como repartidor."))

    def action_confirm(self):
        if self._is_repartidor_only_user():
            raise AccessError(_("No tiene permisos para confirmar pedidos."))
        invalid = self.filtered(lambda order: order.state != "draft")
        if invalid:
            raise UserError(_("Solo se pueden confirmar pedidos en borrador."))
        self.write({"state": "confirmed"})

    def action_assign(self):
        if self._is_repartidor_only_user():
            raise AccessError(_("No tiene permisos para asignar pedidos."))
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
        sale_orders = self.sudo().mapped("sale_order_id").filtered(lambda order: order.state != "cancel")
        if sale_orders:
            sale_orders.with_context(skip_delivery_sync=True).action_finalize_delivery_invoicing()

    def action_cancel(self):
        if self._is_repartidor_only_user():
            raise AccessError(_("No tiene permisos para cancelar pedidos."))
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
