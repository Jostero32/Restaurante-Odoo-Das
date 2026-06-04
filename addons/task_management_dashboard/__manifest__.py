{
    "name": "Gestion de Tareas",
    "version": "1.0.0",
    "category": "Productivity",
    "summary": "Creacion, seguimiento y dashboard de tareas",
    "author": "ARCM Solutions",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/task_security.xml",
        "security/ir.model.access.csv",
        "views/task_assignee_views.xml",
        "views/task_task_views.xml",
        "views/task_dashboard_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}