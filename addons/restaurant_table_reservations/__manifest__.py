{
    "name": "Reservas de Mesa Restaurante Casa Vieja",
    "version": "1.0.0",
    "category": "Restaurant/Reservations",
    "summary": "Gestion de mesas y reservas para Restaurante Casa Vieja",
    "author": "ARCM Solutions",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "restaurant_casa_vieja_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/restaurant_table_views.xml",
        "views/table_reservation_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
