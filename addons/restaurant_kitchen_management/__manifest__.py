{
    'name': 'Gestion de Cocina Restaurante Casa Vieja',
    'version': '1.0.0',
    'category': 'Restaurant/Kitchen',
    'summary': 'Tablero de cocina y gestion de ordenes preparables',
    'author': 'ARCM Solutions',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'product',
        'point_of_sale',
        'pos_restaurant',
        'restaurant_casa_vieja_base',
        'restaurant_delivery_orders',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/kitchen_sequence.xml',
        'views/kitchen_order_views.xml',
        'views/product_views.xml',
        'views/delivery_order_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'restaurant_kitchen_management/static/src/js/kitchen_kanban_live.js',
        ],
        'point_of_sale._assets_pos': [
            'restaurant_kitchen_management/static/src/js/kitchen_service.js',
            'restaurant_kitchen_management/static/src/js/kitchen_ready_popup.js',
            'restaurant_kitchen_management/static/src/js/product_screen_kitchen.js',
            'restaurant_kitchen_management/static/src/js/floor_screen_kitchen_status.js',
            'restaurant_kitchen_management/static/src/xml/kitchen_buttons.xml',
            'restaurant_kitchen_management/static/src/xml/kitchen_ready_popup.xml',
            # kitchen_floor_badges.xml deshabilitado: hacia t-inherit de
            # "pos_restaurant.Table", plantilla que no existe en Odoo 18.
            # El badge sobre el mapa de mesas debe reimplementarse por DOM
            # (como en restaurant_table_reservations) si se desea recuperarlo.
            'restaurant_kitchen_management/static/src/scss/kitchen_pos.scss',
        ],
    },
    'installable': True,
    'application': True,
    # Se instala automaticamente cuando sus dependencias (base, delivery, POS)
    # ya estan instaladas. Asi, al instalar/actualizar el resto del sistema,
    # la cocina se incorpora sola sin tener que listarla a mano.
    'auto_install': True,
}
