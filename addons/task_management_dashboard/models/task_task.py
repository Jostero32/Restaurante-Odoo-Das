from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TaskManagementTask(models.Model):
    _name = "task.management.task"
    _description = "Tarea"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, date_deadline asc, id desc"

    name = fields.Char(string="Nombre de la tarea", required=True, tracking=True)
    description = fields.Text(string="Descripcion", tracking=True)
    responsible_id = fields.Many2one(
        "task.management.assignee",
        string="Responsable",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    assignee_ids = fields.Many2many(
        "task.management.assignee",
        "task_management_task_assignee_rel",
        "task_id",
        "assignee_id",
        string="Asignados",
        tracking=True,
    )
    date_deadline = fields.Date(string="Fecha limite", required=True, tracking=True)
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("in_progress", "En progreso"),
            ("blocked", "Bloqueada"),
            ("done", "Finalizada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        required=True,
        default="pending",
        tracking=True,
        copy=False,
    )
    priority = fields.Selection(
        [
            ("0", "Baja"),
            ("1", "Media"),
            ("2", "Alta"),
            ("3", "Critica"),
        ],
        string="Prioridad",
        required=True,
        default="1",
        tracking=True,
        index=True,
    )
    date_completed = fields.Date(string="Fecha de finalizacion", copy=False, tracking=True)
    is_overdue = fields.Boolean(string="Atrasada", compute="_compute_deadline_metrics", search="_search_is_overdue")
    days_to_deadline = fields.Integer(string="Dias para vencer", compute="_compute_deadline_metrics")
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    color = fields.Integer(string="Color")

    def _register_hook(self):
        """Map legacy states to pending after removing them from the workflow."""
        result = super()._register_hook()
        self.env.cr.execute(
            """
            UPDATE task_management_task
               SET state = 'pending'
             WHERE state IN ('draft', 'review')
            """
        )
        return result

    @api.depends("date_deadline", "state")
    def _compute_deadline_metrics(self):
        today = fields.Date.context_today(self)
        for task in self:
            if not task.date_deadline or task.state in ("done", "cancelled"):
                task.days_to_deadline = 0
                task.is_overdue = False
                continue

            delta_days = (task.date_deadline - today).days
            task.days_to_deadline = delta_days
            task.is_overdue = delta_days < 0

    def _search_is_overdue(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError(_("Operacion no soportada para el filtro de atraso."))

        today = fields.Date.context_today(self)
        overdue_domain = [
            ("date_deadline", "<", today),
            ("state", "not in", ("done", "cancelled")),
        ]
        if (operator == "=" and value) or (operator == "!=" and not value):
            return overdue_domain

        return [
            "|",
            ("date_deadline", ">=", today),
            ("state", "in", ("done", "cancelled")),
        ]

    @api.onchange("responsible_id")
    def _onchange_responsible_id(self):
        for task in self:
            if task.responsible_id:
                task.assignee_ids = task.assignee_ids | task.responsible_id

    @api.constrains("date_deadline")
    def _check_date_deadline(self):
        for task in self:
            if task.date_deadline and task.date_deadline.year < 2000:
                raise ValidationError(_("La fecha limite no puede ser menor al anio 2000."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            values = dict(vals)
            if values.get("responsible_id"):
                values.setdefault("assignee_ids", [])
                values["assignee_ids"] = list(values["assignee_ids"]) + [(4, values["responsible_id"])]

            if values.get("state") == "done" and not values.get("date_completed"):
                values["date_completed"] = fields.Date.context_today(self)
            elif values.get("state") and values.get("state") != "done" and "date_completed" not in values:
                values["date_completed"] = False

            prepared_vals_list.append(values)

        return super().create(prepared_vals_list)

    def write(self, vals):
        values = dict(vals)
        if "state" in values and "date_completed" not in values:
            if values["state"] == "done":
                values["date_completed"] = fields.Date.context_today(self)
            else:
                values["date_completed"] = False

        result = super().write(values)

        if values.get("responsible_id") and not self.env.context.get("skip_task_responsible_sync"):
            self.with_context(skip_task_responsible_sync=True).write(
                {"assignee_ids": [(4, values["responsible_id"])]}
            )

        return result

    def _set_state(self, new_state):
        self.write({"state": new_state})

    def action_set_pending(self):
        self._set_state("pending")

    def action_set_in_progress(self):
        self._set_state("in_progress")

    def action_set_blocked(self):
        self._set_state("blocked")

    def action_set_done(self):
        self._set_state("done")

    def action_set_cancelled(self):
        self._set_state("cancelled")
