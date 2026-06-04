from odoo import api, fields, models


class TaskManagementAssignee(models.Model):
    _name = "task.management.assignee"
    _description = "Asignado de Tareas"
    _order = "name asc, id asc"

    name = fields.Char(string="Nombre", required=True)
    email = fields.Char(string="Correo")
    phone = fields.Char(string="Telefono")
    user_id = fields.Many2one(
        "res.users",
        string="Usuario de Odoo",
        domain="[('share', '=', False), ('active', '=', True)]",
        help="Enlace opcional con un usuario interno de Odoo.",
    )
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    task_count = fields.Integer(string="Tareas", compute="_compute_task_count")

    @api.depends("name")
    def _compute_task_count(self):
        Task = self.env["task.management.task"]
        for assignee in self:
            assignee.task_count = Task.search_count([
                "|",
                ("responsible_id", "=", assignee.id),
                ("assignee_ids", "in", assignee.id),
            ])

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env.ref("task_management_dashboard.action_task_management_task").read()[0]
        action["domain"] = [
            "|",
            ("responsible_id", "=", self.id),
            ("assignee_ids", "in", self.id),
        ]
        action["context"] = {
            "default_responsible_id": self.id,
        }
        return action
