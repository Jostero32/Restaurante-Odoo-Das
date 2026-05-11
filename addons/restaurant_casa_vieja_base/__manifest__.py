{
    'name': 'Base Restaurante Casa Vieja',
    'version': '1.0.0',
    'category': 'Restaurant/Base',
    'summary': 'Configuración base, grupos y menú común para los módulos del Restaurante Casa Vieja',
    'description': """
Base Restaurante Casa Vieja
===========================

Módulo base desarrollado por ARCM Solutions para el proyecto académico
del Restaurante Casa Vieja. Provee los elementos comunes consumidos por
los demás módulos personalizados:

- Categoría y grupos de seguridad propios del restaurante.
- Menú raíz "Restaurante Casa Vieja".
""",
    'author': 'ARCM Solutions',
    'website': 'https://www.arcmsolutions.local',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
    ],

    'data': [
        'security/security.xml',
        'views/menu.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
}
