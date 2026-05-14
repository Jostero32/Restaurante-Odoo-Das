{
    "name": "Pedidos Delivery Restaurante Casa Vieja",
    "version": "1.0.0",
    "category": "Restaurant/Delivery",
    "summary": "Gestion de pedidos a domicilio para Restaurante Casa Vieja",
    "author": "ARCM Solutions",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "restaurant_casa_vieja_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/delivery_order_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
