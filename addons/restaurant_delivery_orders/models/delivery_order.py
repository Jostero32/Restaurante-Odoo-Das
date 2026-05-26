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
    incident_count = fields.Integer(string="Total incidencias", compute="_compute_incident_count")
    customer_status_label = fields.Char(string="Estado para cliente", compute="_compute_customer_status_label")

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

    def _get_customer_state_label(self, state_value=None):
        mapping = {
            "draft": _("En preparacion"),
            "confirmed": _("En preparacion"),
            "assigned": _("En preparacion"),
            "on_route": _("En camino"),
            "delivered": _("Entregado"),
            "cancelled": _("Cancelado"),
        }
        return mapping.get(state_value or self.state, _("En proceso"))

    @api.depends("state")
    def _compute_customer_status_label(self):
        for order in self:
            order.customer_status_label = order._get_customer_state_label(order.state)

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
        if not self.env.context.get("skip_delivery_customer_notify"):
            orders._notify_customer_status_change(force_states={"confirmed", "assigned", "on_route"})
        if not self.env.context.get("skip_delivery_internal_notify"):
            orders._notify_internal_new_website_order()
        return orders

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
            "restaurant_casa_vieja_base.group_restaurant_administracion",
            "restaurant_casa_vieja_base.group_restaurant_administrador",
        ]:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                users |= group.sudo().users.filtered(lambda user: user.active and not user.share)
        if not users:
            return

        model_id = self.env["ir.model"]._get_id("restaurant.delivery.order")
        deadline = fields.Date.context_today(self)
        activity_vals = []
        for order in website_orders:
            order.sudo().message_post(
                body=_(
                    "Nuevo pedido web confirmado. Estado operativo: En preparacion. "
                    "Revisar alistamiento y asignacion de ruta."
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            for user in users:
                activity_vals.append(
                    {
                        "activity_type_id": todo_type.id,
                        "res_model_id": model_id,
                        "res_id": order.id,
                        "user_id": user.id,
                        "summary": _("Nuevo pedido web - asignar repartidor"),
                        "note": _("Pedido %s recibido. Asignar repartidor y confirmar despacho.") % (order.name,),
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
        previous_drivers = {order.id: order.driver_id.id for order in self}
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
        # Si cambio el repartidor asignado: notificar al nuevo y limpiar viejos.
        if "driver_id" in vals:
            driver_changed = self.filtered(
                lambda o: previous_drivers.get(o.id) != o.driver_id.id and o.driver_id
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
            if not partner or not partner.email:
                continue
            email_values = {"email_to": partner.email}
            if template:
                template.sudo().send_mail(order.id, force_send=False, email_values=email_values)
            order.message_post(
                body=_("Actualizacion de estado enviada al cliente: %s", order._get_customer_state_label()),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

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

    def action_cancel(self):
        if self._is_repartidor_only_user():
            raise AccessError(_("No tiene permisos para cancelar pedidos."))
        delivered = self.filtered(lambda order: order.state == "delivered")
        if delivered:
            raise UserError(_("No puede cancelar un pedido entregado."))
        self.write({"state": "cancelled"})
