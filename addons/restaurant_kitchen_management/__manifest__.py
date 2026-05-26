{
    'name': 'Gestión de Cocina - Restaurante Casa Vieja',
    'version': '1.0.0',
    'category': 'Restaurant/Kitchen',
    'summary': 'Gestión de órdenes de cocina para el Restaurante Casa Vieja',
    'description': """
Gestión de Cocina - Restaurante Casa Vieja
==========================================

Módulo desarrollado por ARCM Solutions para el proyecto académico del
Restaurante Casa Vieja. Provee la pantalla de cocina (KDS) para gestionar
las órdenes de preparación:

- Órdenes de cocina generadas desde delivery, POS o de forma manual.
- Vista Kanban agrupada por estado para el personal de cocina.
- Trazabilidad de tiempos: recibido → preparando → listo → servido.
- Campo kitchen_preparable en productos para filtrar qué va a cocina.
""",
    'author': 'ARCM Solutions',
    'website': 'https://www.arcmsolutions.local',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'product',
        'restaurant_casa_vieja_base',
        'restaurant_delivery_orders',
        'restaurant_table_reservations',
    ],

    'data': [
        'data/kitchen_sequence.xml',
        'security/ir.model.access.csv',
        'views/kitchen_order_views.xml',
        'views/product_views.xml',
        'views/menu.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
