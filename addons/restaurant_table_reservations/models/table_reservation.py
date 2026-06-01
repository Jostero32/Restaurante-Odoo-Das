from datetime import timedelta
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


POS_RESERVATION_BUS_CHANNEL = "restaurant_table_reservations.snapshot"
POS_RESERVATION_BUS_NOTIFICATION = "restaurant_table_reservations.snapshot_changed"


class RestaurantTableReservation(models.Model):
    _name = "restaurant.table.reservation"
    _description = "Reserva de mesa"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"

    RESERVATION_MINUTES = 60
    BUFFER_MINUTES = 15

    name = fields.Char(string="Referencia", required=True, default=lambda self: _("Nueva reserva"), copy=False)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cuenta del cliente",
        tracking=True,
        index=True,
        help="Usuario portal que creo la reserva. Permite acceso desde Mis Reservas.",
    )
    customer_name = fields.Char(string="Cliente", required=True, tracking=True)
    customer_phone = fields.Char(string="Telefono", tracking=True)
    party_size = fields.Integer(string="Personas", required=True, default=2, tracking=True)
    zone = fields.Selection(
        [
            ("main", "Interior"),
            ("patio", "Patio"),
        ],
        string="Zona preferida",
        required=True,
        default="main",
        tracking=True,
    )
    table_id = fields.Many2one("restaurant.table", string="Mesa", required=True, tracking=True)
    start_datetime = fields.Datetime(string="Inicio", required=True, tracking=True)
    end_datetime = fields.Datetime(string="Fin", required=True, tracking=True)
    notes = fields.Text(string="Notas")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmada"),
            ("seated", "Sentados"),
            ("done", "Finalizada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    arrangement_type = fields.Selection(
        [
            ('none', 'Ninguno'),
            ('birthday', 'Decoración Cumpleaños'),
            ('anniversary', 'Decoración Aniversario'),
            ('romantic', 'Decoración Cita Romántica'),
            ('general', 'Decoración Normal'),
        ],
        string="Tipo de arreglo (legado)",
        default='none',
        tracking=True,
    )

    arrangement_product_id = fields.Many2one(
        'product.template',
        string="Arreglo Especial para la mesa",
        domain=[('type', '=', 'service')],
        tracking=True,
    )

    arrangement_charged = fields.Boolean(
        string="Arreglo Cobrado",
        default=False,
        help="Indica si el cargo por arreglo ya fue añadido a la orden POS para evitar dobles cargos.",
    )

    # ------------------------------------------------------------------
    # Pre-orden
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    pre_order_line_ids = fields.One2many(
        "restaurant.table.reservation.line",
        "reservation_id",
        string="Pre-orden",
        copy=False,
    )
    pre_order_total = fields.Monetary(
        string="Total pre-orden",
        compute="_compute_pre_order_totals",
        store=True,
        currency_field="currency_id",
    )
    pre_order_count = fields.Integer(
        string="Items pre-orden",
        compute="_compute_pre_order_totals",
        store=True,
    )
    pre_order_lines_charged = fields.Boolean(
        default=False,
        copy=False,
        help="Las lineas de pre-orden ya fueron volcadas al POS para evitar duplicados.",
    )

    @api.depends("pre_order_line_ids.price_subtotal", "pre_order_line_ids.qty")
    def _compute_pre_order_totals(self):
        for reservation in self:
            reservation.pre_order_total = sum(reservation.pre_order_line_ids.mapped("price_subtotal"))
            reservation.pre_order_count = int(sum(reservation.pre_order_line_ids.mapped("qty")))

    def _get_arrangement_cost(self):
        """Return the numeric cost: prefer arrangement_product_id, fallback to legacy type."""
        if self.arrangement_product_id:
            return self.arrangement_product_id.list_price
        if not self.arrangement_type or self.arrangement_type == 'none':
            return 0.0
        default_code = self._ARRANGEMENT_CODE_MAP.get(self.arrangement_type)
        if default_code:
            product = self.env['product.template'].sudo().search(
                [('default_code', '=', default_code)], limit=1
            )
            if product:
                return product.list_price
        return 0.0

    # ------------------------------------------------------------------
    # Onchange helpers
    # ------------------------------------------------------------------

    @api.onchange("start_datetime")
    def _onchange_start_datetime(self):
        for reservation in self:
            if reservation.start_datetime:
                reservation.end_datetime = reservation._get_end_datetime(reservation.start_datetime)

    @api.onchange("zone", "party_size")
    def _onchange_zone_party_size(self):
        for reservation in self:
            if reservation.table_id and (
                reservation.table_id.zone != reservation.zone
                or reservation.table_id.seats < reservation.party_size
            ):
                reservation.table_id = False

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    @api.model
    def _get_end_datetime(self, start_datetime):
        return start_datetime + timedelta(minutes=self.RESERVATION_MINUTES + self.BUFFER_MINUTES)

    @api.model
    def _get_business_schedule(self):
        # Reusamos el horario configurado en delivery: feriados y franjas
        # operativas son los mismos para reservas en sitio.
        Schedule = self.env["restaurant.delivery.schedule"].sudo()
        return Schedule._get_or_create_for_company(self.env.company)

    @api.model
    def _get_schedule_status_for_date(self, date_value):
        if not date_value:
            return {"is_open": True, "message": ""}
        selected_date = fields.Date.from_string(date_value) if isinstance(date_value, str) else date_value
        schedule = self._get_business_schedule()
        exception = schedule._exception_for_date(selected_date)
        if exception and exception.is_closed:
            return {
                "is_open": False,
                "message": _("Cerrado el %(date)s: %(reason)s.") % {
                    "date": selected_date.isoformat(),
                    "reason": exception.name,
                },
            }
        if not schedule._ranges_for_date(selected_date):
            return {
                "is_open": False,
                "message": _("El restaurante no opera ese dia."),
            }
        return {"is_open": True, "message": ""}

    _ARRANGEMENT_CODE_MAP = {
        'birthday': 'ARR-BIRTHDAY',
        'anniversary': 'ARR-ANNIV',
        'romantic': 'ARR-ROMANTIC',
        'general': 'ARR-GENERAL',
    }

    _ARRANGEMENT_NAMES = [
        'Decoración Cumpleaños',
        'Decoración Aniversario',
        'Decoración Cita Romántica',
        'Decoración Normal',
    ]

    @api.model
    def _get_arrangement_products(self):
        """Return the 4 arrangement service products for the website form.

        Searches first by 'Arreglos de Mesa' category; falls back to exact
        name matching so user-created products without the category still work.
        """
        category = self.env['product.category'].sudo().search(
            [('name', '=', 'Arreglos de Mesa')], limit=1
        )
        if category:
            products = self.env['product.template'].sudo().search([
                ('categ_id', '=', category.id),
                ('type', '=', 'service'),
            ], order='name asc')
        else:
            products = self.env['product.template'].sudo().search([
                ('name', 'in', self._ARRANGEMENT_NAMES),
                ('type', '=', 'service'),
            ], order='name asc')

        # Deduplicate by name: keep the highest ID (user-created product wins)
        seen = {}
        for p in products:
            if p.name not in seen or p.id > seen[p.name].id:
                seen[p.name] = p

        return [
            {
                'id': p.id,
                'name': p.name,
                'price': p.list_price,
                'label': f"{p.name} +${p.list_price:.2f}",
                'description': p.description_sale or "",
                'image_url': f"/web/image/product.template/{p.id}/image_128",
            }
            for p in seen.values()
        ]

    @api.model
    def _get_pre_order_products(self):
        products = self.env["product.product"].sudo().search(
            [
                ("active", "=", True),
                ("sale_ok", "=", True),
                ("product_tmpl_id.available_for_reservation_preorder", "=", True),
            ],
            order="name asc, id asc",
        )
        result = []
        for product in products:
            result.append(
                {
                    "id": product.id,
                    "name": product.display_name,
                    "price": product.lst_price,
                    "currency_symbol": self.env.company.currency_id.symbol or "$",
                    "uom_name": product.uom_id.name or "",
                    "image_url": f"/web/image/product.product/{product.id}/image_128",
                    "description": product.description_sale or "",
                    "follows_party_size": bool(product.product_tmpl_id.preorder_qty_follows_party_size),
                }
            )
        return result

    @api.model
    def _get_arrangement_label(self, arrangement_type=None, product=None):
        if product:
            return f"{product.name} +${product.list_price:.2f}"
        if not arrangement_type or arrangement_type == 'none':
            return 'Ninguno'
        default_code = self._ARRANGEMENT_CODE_MAP.get(arrangement_type)
        if default_code:
            prod = self.env['product.template'].sudo().search(
                [('default_code', '=', default_code)], limit=1
            )
            if prod:
                return f"{prod.name} +${prod.list_price:.2f}"
        return arrangement_type

    @api.model
    def _get_arrangement_cost_label(self, arrangement_type):
        if not arrangement_type or arrangement_type == 'none':
            return ''
        default_code = self._ARRANGEMENT_CODE_MAP.get(arrangement_type)
        if default_code:
            product = self.env['product.template'].sudo().search(
                [('default_code', '=', default_code)], limit=1
            )
            if product:
                return f"+${product.list_price:.2f}"
        return ''

    @api.model
    def _validate_requested_start_datetime(self, start_datetime):
        current_utc = fields.Datetime.now()
        if start_datetime < current_utc:
            raise ValidationError(_("No puedes reservar en un horario anterior al momento actual."))
        schedule = self._get_business_schedule()
        local_start = schedule._to_company_local(start_datetime)
        local_date = local_start.date()
        exception = schedule._exception_for_date(local_date)
        if exception and exception.is_closed:
            raise ValidationError(_("El restaurante esta cerrado el %(date)s: %(reason)s.") % {
                "date": local_date.isoformat(),
                "reason": exception.name,
            })
        ranges = schedule._ranges_for_date(local_date)
        if not ranges:
            raise ValidationError(_("El restaurante no opera ese dia."))
        start_decimal = local_start.hour + local_start.minute / 60.0
        end_decimal = start_decimal + self.RESERVATION_MINUTES / 60.0
        for time_from, time_to in ranges:
            if time_from <= start_decimal and end_decimal <= time_to:
                return
        raise ValidationError(_(
            "La hora seleccionada no encaja en el horario operativo. "
            "Recuerda que la reserva dura %(min)s minutos."
        ) % {"min": self.RESERVATION_MINUTES})

    @api.model
    def _get_time_options(self, date_value):
        """Return allowed time options for a given date based on the business schedule."""
        if not date_value:
            return []
        selected_date = fields.Date.from_string(date_value)
        schedule = self._get_business_schedule()
        ranges = schedule._ranges_for_date(selected_date)
        if not ranges:
            return []
        step_minutes = schedule.slot_minutes or 15
        today_local = fields.Date.context_today(self)
        now_decimal = None
        if selected_date == today_local:
            now_local = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            now_decimal = now_local.hour + now_local.minute / 60.0
        reservation_hours = self.RESERVATION_MINUTES / 60.0
        options = []
        seen = set()
        for time_from, time_to in ranges:
            # Solo ofrecemos inicios cuyos 60 min de reserva caigan dentro de la franja.
            max_start_decimal = time_to - reservation_hours
            if max_start_decimal < time_from:
                continue
            start_minutes = int(round(time_from * 60))
            max_minutes = int(round(max_start_decimal * 60))
            for minutes in range(start_minutes, max_minutes + 1, step_minutes):
                decimal = minutes / 60.0
                if now_decimal is not None and decimal < now_decimal:
                    continue
                label = f"{minutes // 60:02d}:{minutes % 60:02d}"
                if label in seen:
                    continue
                seen.add(label)
                options.append(label)
        return options

    @api.model
    def _get_floor_ids_for_zone(self, zone):
        """Return floor IDs that match a given zone code."""
        floors = self.env["restaurant.floor"].sudo().search([])
        zone_keyword = {"main": "interior", "patio": "patio"}.get(zone, "")
        return [
            f.id for f in floors
            if zone_keyword and zone_keyword in (f.name or "").strip().lower()
        ]

    @api.model
    def _get_available_tables(self, start_datetime, party_size, zone=None, exclude_reservation_id=None):
        """Return available tables as a list of dicts with uniform keys."""
        end_datetime = self._get_end_datetime(start_datetime)

        sql = [
            "SELECT t.id,",
            "  COALESCE(t.table_number, 0) AS table_number,",
            "  COALESCE(t.seats, 0) AS seats,",
            "  COALESCE(f.name, '') AS floor_name",
            "FROM restaurant_table t",
            "LEFT JOIN restaurant_floor f ON f.id = t.floor_id",
            "WHERE t.active IS TRUE",
        ]
        params = []

        if zone:
            floor_ids = self._get_floor_ids_for_zone(zone)
            if floor_ids:
                sql.append("AND t.floor_id IN %s")
                params.append(tuple(floor_ids))
            else:
                # No valid floors for this zone → return empty
                return []

        sql.append("ORDER BY t.table_number ASC")
        self.env.cr.execute(" ".join(sql), params)
        tables = self.env.cr.dictfetchall()

        available_tables = []
        for table in tables:
            if table["seats"] < party_size:
                continue

            overlap_domain = [
                ("id", "!=", exclude_reservation_id or 0),
                ("table_id", "=", table["id"]),
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ]
            if not self.search_count(overlap_domain):
                # Determine zone from floor name
                fname = (table["floor_name"] or "").strip().lower()
                if "interior" in fname:
                    table_zone = "main"
                elif "patio" in fname:
                    table_zone = "patio"
                else:
                    table_zone = ""

                available_tables.append({
                    "id": table["id"],
                    "name": str(table["table_number"]),
                    "capacity": table["seats"],
                    "zone": table_zone,
                    "notes": "",
                })

        return available_tables

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model
    def _sync_reservation_window(self, vals):
        if vals.get("start_datetime"):
            start_datetime = fields.Datetime.to_datetime(vals["start_datetime"])
            vals["end_datetime"] = fields.Datetime.to_string(self._get_end_datetime(start_datetime))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        synced_vals_list = [self._sync_reservation_window(dict(vals)) for vals in vals_list]
        for vals in synced_vals_list:
            if vals.get("start_datetime"):
                self._validate_requested_start_datetime(fields.Datetime.to_datetime(vals["start_datetime"]))
            if vals.get("arrangement_type"):
                vals["arrangement_type"] = vals["arrangement_type"] or "none"
        reservations = super().create(synced_vals_list)
        if not self.env.context.get("skip_reservation_internal_notify"):
            reservations._notify_internal_new_reservation()
        return reservations

    def _notify_internal_new_reservation(self):
        web_reservations = self.filtered(lambda r: r.partner_id)
        if not web_reservations:
            return
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo_type:
            return
        users = self.env["res.users"]
        for group_xmlid in [
            "restaurant_casa_vieja_base.group_restaurant_mesero",
            "restaurant_casa_vieja_base.group_restaurant_administracion",
            "restaurant_casa_vieja_base.group_restaurant_administrador",
        ]:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                users |= group.sudo().users.filtered(lambda u: u.active and not u.share)
        if not users:
            return
        model_id = self.env["ir.model"]._get_id("restaurant.table.reservation")
        activity_vals = []
        for reservation in web_reservations:
            deadline = fields.Date.to_date(reservation.start_datetime) if reservation.start_datetime else fields.Date.context_today(self)
            zone_label = dict(self._fields["zone"].selection).get(reservation.zone, reservation.zone)
            arrangement_label = self._get_arrangement_label(reservation.arrangement_type)
            summary = _("Nueva reserva web: %(name)s (%(party)s pers, mesa %(table)s)") % {
                "name": reservation.customer_name,
                "party": reservation.party_size,
                "table": reservation.table_id.table_number or "-",
            }
            note = _(
                "Reserva %(ref)s para el %(when)s en %(zone)s. Arreglo: %(arrangement)s. Telefono: %(phone)s."
            ) % {
                "ref": reservation.name,
                "when": fields.Datetime.to_string(reservation.start_datetime),
                "zone": zone_label,
                "arrangement": arrangement_label,
                "phone": reservation.customer_phone or _("sin telefono"),
            }
            reservation.sudo().message_post(
                body=_("Nueva reserva web recibida desde el portal. Revisar agenda y arreglo si aplica."),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            for user in users:
                activity_vals.append({
                    "activity_type_id": todo_type.id,
                    "res_model_id": model_id,
                    "res_id": reservation.id,
                    "user_id": user.id,
                    "summary": summary,
                    "note": note,
                    "date_deadline": deadline,
                })
        if activity_vals:
            self.env["mail.activity"].sudo().create(activity_vals)

    def write(self, vals):
        if vals.get("start_datetime"):
            vals = dict(vals)
            start_datetime = fields.Datetime.to_datetime(vals["start_datetime"])
            self._validate_requested_start_datetime(start_datetime)
            vals["end_datetime"] = fields.Datetime.to_string(self._get_end_datetime(start_datetime))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("party_size", "start_datetime", "end_datetime", "table_id", "state")
    def _check_reservation_rules(self):
        for reservation in self:
            if reservation.party_size <= 0:
                raise ValidationError(_("La cantidad de personas debe ser mayor a cero."))
            if reservation.table_id and reservation.party_size > reservation.table_id.seats:
                raise ValidationError(_("La reserva supera la capacidad de la mesa seleccionada."))
            if reservation.table_id and reservation.table_id.zone != reservation.zone:
                raise ValidationError(_("La mesa seleccionada no coincide con la zona preferida."))
            if reservation.start_datetime and reservation.end_datetime:
                if reservation.end_datetime <= reservation.start_datetime:
                    raise ValidationError(_("La hora de fin debe ser posterior a la hora de inicio."))
            if not reservation.table_id or reservation.state in ("cancelled", "done"):
                continue
            domain = [
                ("id", "!=", reservation.id),
                ("table_id", "=", reservation.table_id.id),  
                ("state", "not in", ("cancelled", "done")),
                ("start_datetime", "<", reservation.end_datetime),
                ("end_datetime", ">", reservation.start_datetime),
            ]
            if reservation.start_datetime and reservation.end_datetime and self.search_count(domain):
                raise ValidationError(_("Ya existe una reserva activa para esa mesa en el horario indicado."))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_confirm(self):
        self.write({"state": "confirmed"})
        self._notify_pos_reservation_change()

    def _create_pos_order_for_reservation(self):
        """Create an empty draft POS order for the table so it appears occupied in the floor map."""
        session = self.env['pos.session'].sudo().search(
            [('state', '=', 'opened')], limit=1
        )
        if not session:
            return
        for reservation in self:
            if not reservation.table_id:
                continue
            already_open = self.env['pos.order'].sudo().search_count([
                ('table_id', '=', reservation.table_id.id),
                ('state', '=', 'draft'),
                ('session_id', '=', session.id),
            ])
            if already_open:
                continue
            self.env['pos.order'].sudo().create({
                'session_id': session.id,
                'table_id': reservation.table_id.id,
                'state': 'draft',
                'partner_id': reservation.partner_id.id if reservation.partner_id else False,
                'amount_tax': 0.0,
                'amount_total': 0.0,
                'amount_paid': 0.0,
                'amount_return': 0.0,
                'pos_reference': '',
            })

    def action_seated(self):
        self.write({"state": "seated"})
        self._create_pos_order_for_reservation()
        self._inject_pre_order_lines_into_pos_order()
        self._notify_pos_reservation_change()

    def action_done(self):
        self.write({"state": "done"})
        self._notify_pos_reservation_change()

    def action_cancel(self):
        active = self.filtered(lambda reservation: reservation.state in ("seated", "done"))
        if active:
            raise UserError(_("No puede cancelar una reserva sentada o finalizada."))
        self.write({"state": "cancelled", "arrangement_charged": False})
        for reservation in self:
            reservation.activity_ids.filtered(lambda a: a.res_model == "restaurant.table.reservation").unlink()
        self._notify_pos_reservation_change()

    # ------------------------------------------------------------------
    # Volcado del pre-orden al POS al sentar a los clientes
    # ------------------------------------------------------------------

    def _inject_pre_order_lines_into_pos_order(self):
        PosOrder = self.env["pos.order"].sudo()
        PosOrderLine = self.env["pos.order.line"].sudo()
        for reservation in self:
            if reservation.pre_order_lines_charged or not reservation.pre_order_line_ids:
                continue
            order = PosOrder.search(
                [
                    ("table_id", "=", reservation.table_id.id),
                    ("state", "=", "draft"),
                ],
                order="id desc",
                limit=1,
            )
            if not order:
                continue
            for line in reservation.pre_order_line_ids:
                already = order.lines.filtered(
                    lambda ol: ol.product_id == line.product_id and ol.reservation_id == reservation
                )
                if already:
                    continue
                pos_line_vals = {
                    "order_id": order.id,
                    "product_id": line.product_id.id,
                    "qty": line.qty,
                    "price_unit": line.price_unit,
                    "reservation_id": reservation.id,
                }
                preface = _("Pre-orden reserva %s.") % reservation.name
                pos_line_vals["note"] = (
                    f"{preface} {line.notes}" if line.notes else preface
                )
                PosOrderLine.create(pos_line_vals)
            reservation.sudo().write({"pre_order_lines_charged": True})

    def _notify_pos_reservation_change(self, table_ids=None):
        self.env["bus.bus"]._sendone(
            POS_RESERVATION_BUS_CHANNEL,
            POS_RESERVATION_BUS_NOTIFICATION,
            {"table_ids": table_ids or self.mapped("table_id").ids},
        )
