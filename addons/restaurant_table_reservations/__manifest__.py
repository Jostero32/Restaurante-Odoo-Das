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
        "website",
        "pos_restaurant",
        "point_of_sale",
        "restaurant_casa_vieja_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/restaurant_table_views.xml",
        "views/table_reservation_views.xml",
        "views/reservation_website_templates.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "restaurant_table_reservations/static/src/css/reservation.css",
            "restaurant_table_reservations/static/src/js/reservation.js",
        ],
        "point_of_sale.assets": [
            "restaurant_table_reservations/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
