# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y el proyecto adhiere, en lo posible, a
[Versionado Semántico](https://semver.org/lang/es/).

## [No publicado]

### Por hacer
- Automatización de pruebas funcionales y de regresión.
- Pipeline de CI/CD.
- Módulo de cocina (tablero Kanban, pantalla de mesero) — ver
  [docs/09_hallazgos_mejoras.md](docs/09_hallazgos_mejoras.md).

## [1.0.0] - 2026-05-31

Primera versión documentada del sistema. Esta entrega corresponde a la
**documentación inicial** del estado funcional existente de los módulos.

### Añadido (documentación)
- Documentación inicial del **módulo base** `restaurant_casa_vieja_base`
  (categoría, grupos de seguridad y menú raíz).
- Documentación inicial del **módulo de pedidos a domicilio**
  `restaurant_delivery_orders`: modelos, estados, portal, rutas web,
  integración con `sale.order` y facturación, asignación de repartidores,
  incidencias, calificaciones, horarios de entrega y notificaciones.
- Documentación inicial del **módulo de reservas de mesa**
  `restaurant_table_reservations`: modelos, estados, validaciones, zonas,
  mesas, pre-orden de productos, arreglos especiales, integración con POS y
  rutas web del portal.
- Documentación de la **integración de pagos Kushki** (`pay_kushki`) como
  integración complementaria del flujo web/e-commerce/delivery.
- Documentos del taller en `docs/`:
  - Descripción general (`01_descripcion_general.md`).
  - Manual de usuario (`02_manual_usuario.md`).
  - Documentación técnica (`03_documentacion_tecnica.md`).
  - Integraciones (`04_integraciones.md`).
  - Instalación con Docker (`05_instalacion_docker.md`).
  - Plan de pruebas (`06_plan_pruebas.md`).
  - Casos de prueba funcionales (`07_casos_prueba_funcionales.md`).
  - Prueba de rendimiento con JMeter (`08_prueba_rendimiento_jmeter.md`).
  - Hallazgos y mejoras (`09_hallazgos_mejoras.md`).
  - Guía de evidencias (`docs/evidencias/README.md`).
- Archivos de gobernanza del repositorio: `README.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md` y este `CHANGELOG.md`.

### Notas
- Esta versión documenta el código **tal como existe**; no introduce cambios
  funcionales en Python, XML, JavaScript ni en la configuración de Docker.
- El módulo de cocina **no está desarrollado**; aparece únicamente como mejora
  futura.

[No publicado]: https://github.com/Jostero32/Restaurante-Odoo-Das/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Jostero32/Restaurante-Odoo-Das/releases/tag/v1.0.0
