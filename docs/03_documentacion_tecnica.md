# 03 — Documentación Técnica

Documentación dirigida a **desarrolladores**. Describe la arquitectura técnica,
los modelos, campos, métodos, estados, seguridad, vistas y controladores de cada
módulo, así como su integración con Odoo estándar.

> Solo se documenta lo que existe en el código. Lo no confirmado se marca como
> *pendiente de validar* o *si aplica*.

---

## 1. Arquitectura técnica

El sistema es una aplicación **Odoo 18** compuesta por cuatro módulos en
`addons/`, sobre PostgreSQL 15, orquestada con Docker Compose.

```
restaurant_casa_vieja_base   (base: grupos + menú raíz)
        ▲                ▲
        │                │
restaurant_delivery_orders │
        ▲                  │
        │                  │
restaurant_table_reservations  ──► depende también de delivery_orders

pay_kushki  (independiente: payment / website_sale / website_payment)
```

Cada módulo sigue la estructura estándar de Odoo: `__manifest__.py`, `models/`,
`controllers/`, `views/`, `security/`, `data/` y `static/`.

## 2. Dependencias entre módulos

| Módulo | `depends` declarado |
|--------|---------------------|
| `restaurant_casa_vieja_base` | `base`, `mail` |
| `restaurant_delivery_orders` | `base`, `mail`, `portal`, `sale_management`, `account`, `restaurant_casa_vieja_base`, `website_sale`, `l10n_ec_website_sale` |
| `restaurant_table_reservations` | `base`, `mail`, `website`, `pos_restaurant`, `point_of_sale`, `restaurant_casa_vieja_base`, `restaurant_delivery_orders` |
| `pay_kushki` | `website_sale`, `payment`, `website_payment` |

Observaciones:
- `restaurant_table_reservations` **depende de** `restaurant_delivery_orders`
  porque reutiliza el modelo de horario (`restaurant.delivery.schedule`) para las
  validaciones de horario operativo de las reservas.
- `pay_kushki` es **independiente** de los módulos del restaurante; se integra
  por el flujo estándar de pagos de Odoo.

---

## 3. Módulo `restaurant_casa_vieja_base`

Módulo **base común**. No define modelos de negocio; aporta la categoría de
seguridad, los grupos de roles y el menú raíz que consumen los demás módulos.

### 3.1 Seguridad (`security/security.xml`)

- **Categoría:** `module_category_restaurant_casa_vieja` ("Restaurante Casa Vieja").
- **Grupos** (`res.groups`):

| XML ID | Nombre | Hereda | Comentario |
|--------|--------|--------|------------|
| `group_restaurant_repartidor` | Repartidor Restaurante | `base.group_user` | Lee pedidos asignados y actualiza su estado. |
| `group_restaurant_cocinero` | Cocinero Restaurante | `base.group_user` | Solo lectura sobre modelos operativos. |
| `group_restaurant_mesero` | Mesero Restaurante | `base.group_user` | Toma reservas y pedidos; no elimina. |
| `group_restaurant_administracion` | Administración Restaurante | `base.group_user`, mesero, cocinero | Crea y edita; no elimina. |
| `group_restaurant_administrador` | Administrador Restaurante | `base.group_user`, administración, cocinero | Control total (CRUD). |

### 3.2 Menú (`views/menu.xml`)

- `menu_restaurant_casa_vieja_root` — menú raíz "Restaurante Casa Vieja",
  visible para todos los grupos del restaurante. Los demás módulos cuelgan sus
  menús de este nodo.

> El grupo **Cocinero** existe en la base, pero **no hay un módulo de cocina**
> asociado. Su alcance se limita a lectura. La cocina figura solo como mejora
> futura ([09_hallazgos_mejoras.md](09_hallazgos_mejoras.md)).

---

## 4. Módulo `restaurant_delivery_orders`

Módulo **principal** de pedidos a domicilio. Integra e-commerce, ventas,
facturación, portal y notificaciones.

### 4.1 Modelos principales

| Modelo | Archivo | Descripción |
|--------|---------|-------------|
| `restaurant.delivery.order` | `models/delivery_order.py` | Pedido a domicilio. |
| `restaurant.delivery.incident` | `models/delivery_incident.py` | Incidencia de un pedido. |
| `restaurant.delivery.rating` | `models/delivery_rating.py` | Calificación de un pedido entregado. |
| `restaurant.delivery.schedule` | `models/delivery_schedule.py` | Horario de delivery por compañía. |
| `restaurant.delivery.schedule.line` | `models/delivery_schedule.py` | Franja semanal del horario. |
| `restaurant.delivery.schedule.exception` | `models/delivery_schedule.py` | Excepción/feriado del horario. |

Modelos heredados (Odoo estándar):

| Modelo heredado | Archivo | Aporte |
|-----------------|---------|--------|
| `sale.order` | `models/sale_order.py` | Sincronización con el pedido de delivery, facturación y entrega programada. |
| `sale.order.line` | `models/sale_order_line.py` | Línea técnica del costo de envío y disparo de sincronización. |
| `res.company` | `models/res_company.py` | Costo fijo y producto de envío. |
| `res.users` | `models/res_users.py` | Promedio de calificaciones como repartidor. |
| `product.template` | `models/product_template.py` | Campos de ETA, porción, ingredientes, alérgenos para la web. |

### 4.2 `restaurant.delivery.order` — campos relevantes

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Referencia (secuencia `restaurant.delivery.order`). |
| `customer_name`, `customer_phone` | Char | Datos del cliente. |
| `partner_id` | Many2one `res.partner` | Cliente (enlace al contacto). |
| `delivery_address` | Char | Dirección de entrega. |
| `order_datetime` | Datetime | Fecha del pedido. |
| `eta_minutes` | Integer | ETA en minutos (default 35). |
| `estimated_delivery_datetime` | Datetime (compute, store) | Fecha estimada = `order_datetime` + ETA. |
| `amount_total` | Monetary | Total del pedido. |
| `driver_id` | Many2one `res.users` | Repartidor (con dominio que filtra el grupo Repartidor). |
| `state` | Selection | Estado del pedido (ver 4.3). |
| `sale_order_id` | Many2one `sale.order` | Venta de origen. |
| `is_scheduled`, `scheduled_for` | Boolean / Datetime | Entrega programada. |
| `product_summary` | Text (compute) | Resumen de productos desde la venta. |
| `linked_invoice_ids`, `invoice_*` | (compute) | Métricas de facturación asociada. |
| `incident_ids` | One2many | Incidencias del pedido. |
| `customer_rating_ids`, `rating_score`, `rating_comment`, `has_rating` | | Calificación. |
| `display_state_key`, `customer_status_label` | Char (compute) | Estado visible al cliente (simplificado). |

### 4.3 Estados de `restaurant.delivery.order`

| Valor | Etiqueta interna |
|-------|------------------|
| `draft` | Recibido |
| `confirmed` | En preparación |
| `assigned` | Asignado |
| `on_route` | En camino |
| `delivered` | Entregado |
| `cancelled` | Cancelado |

Existe además un estado **visual** `scheduled_received` ("Pedido recibido") que
se deriva para pedidos programados cuya hora de preparación aún no llega
(umbral `_PREP_LEAD_MINUTES = 90`).

### 4.4 Métodos relevantes de `restaurant.delivery.order`

| Método | Propósito |
|--------|-----------|
| `_driver_domain()` | Dominio para `driver_id`: usuarios del grupo Repartidor que no sean Administrador. |
| `create()` / `write()` / `unlink()` | Aplican restricciones por rol (repartidor solo edita `state`/`notes`, no crea ni elimina) y disparan notificaciones. |
| `action_confirm()` | `draft` → `confirmed`. |
| `action_assign()` | `confirmed` → `assigned` (exige repartidor). |
| `action_on_route()` | `assigned` → `on_route` (exige repartidor). |
| `action_delivered()` | `on_route` → `delivered`; finaliza la facturación de la venta. |
| `action_cancel()` | Cancela (no permite cancelar entregados). |
| `_notify_customer_status_change()` | Envía correo (plantilla) y mensaje al chat del portal ante cambios de estado. |
| `_notify_internal_new_website_order()` | Crea actividades para el personal ante pedidos web nuevos. |
| `_sync_chat_followers()` | Suscribe cliente y repartidor al chatter del pedido. |
| `_resolve_display_state_key()` | Calcula el estado visual para el cliente. |
| `_check_eta_minutes()`, `_check_scheduled_for()`, `_check_driver_role()` | Restricciones (`@api.constrains`). |

> El modelo también contiene métodos de mantenimiento/migración invocables por
> shell (p. ej. `_migrate_legacy_delivery_orders`, `_lockdown_repartidor_backend_menus`,
> `_enforce_single_address_storefront`). Son utilitarios de configuración, no
> parte del flujo de usuario.

### 4.5 `restaurant.delivery.incident`

- Campos: `name` (secuencia), `delivery_order_id`, `partner_id`, `issue_type`
  (`incomplete`, `cold`, `delay`, `wrong_item`, `other`), `description`, `state`
  (`new`, `in_review`, `resolved`, `rejected`), `resolution_notes`,
  `reported_datetime`.
- Métodos: `action_in_review()`, `action_resolved()`, `action_rejected()`.
- Al crear, publica un mensaje en el chatter del pedido.

### 4.6 `restaurant.delivery.rating`

- Campos: `delivery_order_id` (único por pedido), `partner_id`, `driver_id`,
  `score` (1–5), `score_int` (compute), `comment`, `rated_at`.
- Restricción `_check_order_delivered()`: solo se puede calificar un pedido en
  estado `delivered`.
- Restricción SQL: una sola calificación por pedido.

### 4.7 `restaurant.delivery.schedule` (y líneas/excepciones)

- Horario **por compañía** (único por `company_id`).
- Parámetros: `slot_minutes` (granularidad), `min_lead_time_minutes`
  (anticipación mínima), `max_schedule_days` (días máximos a futuro).
- `line_ids`: franjas semanales (`day_of_week`, `time_from`, `time_to`).
- `exception_ids`: excepciones por fecha (cerrado o con horario especial).
- Métodos clave: `is_open_at(dt)`, `get_available_slots(date)`,
  `get_available_slots_window()`, conversión de zona horaria
  (`_to_company_local`, `_to_utc`).

### 4.8 Modelos heredados — puntos clave

**`sale.order`** (`models/sale_order.py`):
- Campos añadidos: `delivery_order_id`, `delivery_is_scheduled`,
  `delivery_scheduled_for`.
- `_sync_delivery_order_from_sale()`: crea/actualiza el `restaurant.delivery.order`
  a partir de la venta.
- `action_finalize_delivery_invoicing()`, `action_ensure_invoice()`,
  `_ensure_fixed_delivery_fee_line()`: gestionan la facturación y el costo fijo
  de envío.
- `action_confirm()`, `_action_cancel()`, `write()`: disparan la sincronización
  hacia el pedido de delivery.
- `_validate_scheduled_delivery_slot()`: valida el horario programado.

**`res.company`**: `delivery_fixed_fee`, `delivery_fee_product_id`,
`_get_or_create_delivery_fee_product()`.

**`res.users`**: `delivery_rating_average`, `delivery_rating_count` (promedio de
estrellas como repartidor).

**`product.template`**: `delivery_eta_min`, `delivery_eta_max`,
`delivery_portion_label`, `delivery_ingredients`, `delivery_allergens`,
`delivery_incidents_policy` (campos informativos para la ficha web).

### 4.9 Controladores y rutas web

**`controllers/portal_delivery.py`** (hereda `CustomerPortal`):

| Ruta | Método HTTP | Auth | Descripción |
|------|-------------|------|-------------|
| `/my/delivery` , `/my/delivery/page/<int:page>` | GET | user | Lista de pedidos del cliente. |
| `/my/delivery/invoices` , `/my/delivery/invoices/page/<int:page>` | GET | user | Lista de facturas de delivery. |
| `/my/delivery/invoices/<int:invoice_id>` | GET | user | Detalle de una factura. |
| `/my/delivery/<int:order_id>` | GET | public | Detalle del pedido (con token de acceso). |
| `/my/delivery/<int:order_id>/rate` | POST | user | Registrar calificación. |
| `/my/delivery/<int:order_id>/reorder` | POST | user | Reordenar (recrea carrito). |
| `/my/delivery/<int:order_id>/incident` | POST | user | Reportar incidencia. |

**`controllers/website_sale_checkout.py`** (hereda `WebsiteSale`):

| Ruta | Tipo | Auth | Descripción |
|------|------|------|-------------|
| `/shop/delivery_schedule/window` | json | public | Devuelve los slots disponibles para programar entrega. |
| `/shop/delivery_schedule/set` | json | public | Fija/limpia la entrega programada en el carrito. |

También sobreescribe `_get_mandatory_billing_address_fields` para flexibilizar
campos de facturación en el checkout.

### 4.10 Vistas y datos

- Vistas backend: `delivery_order_views.xml`, `delivery_incident_views.xml`,
  `delivery_rating_views.xml`, `delivery_schedule_views.xml`,
  `sale_order_views.xml`, `product_template_views.xml`, `res_company_views.xml`.
- Vistas web/portal: `portal_delivery_templates.xml`, `website_sale_templates.xml`.
- Datos: secuencias (`delivery_sequence.xml`, `delivery_incident_sequence.xml`),
  plantilla de correo (`mail_templates.xml`), horario por defecto
  (`delivery_schedule_default.xml`), limpieza web (`website_cleanup.xml`).
- Assets frontend: `portal_delivery.scss`, `checkout_delivery_schedule.js`,
  `portal_chat_refresh.js`.

### 4.11 Notificaciones

- **Correo:** plantilla `mail_template_delivery_status_update` enviada al cliente
  ante cambios de estado.
- **Chat del portal:** mensajes públicos en el chatter del pedido
  (`_customer_chat_message_for_state`).
- **Actividades internas:** se generan para el personal ante pedidos web nuevos.

---

## 5. Módulo `restaurant_table_reservations`

Módulo **principal** de reservas de mesa, con portal web e integración con el POS.

### 5.1 Modelos principales

| Modelo | Archivo | Descripción |
|--------|---------|-------------|
| `restaurant.table.reservation` | `models/table_reservation.py` | Reserva de mesa. |
| `restaurant.table.reservation.line` | `models/reservation_line.py` | Línea de pre-orden. |
| `restaurant.table` (heredado) | `models/restaurant_table.py` | Mesa del POS, con zona derivada del piso. |
| `product.template` (heredado) | `models/product_template.py` | Campos para pre-orden de reserva. |
| `pos.order.line` (heredado) | `models/pos_order_line.py` | Línea POS enlazada a la reserva. |

### 5.2 `restaurant.table.reservation` — campos relevantes

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Referencia. |
| `partner_id` | Many2one `res.partner` | Cuenta del cliente (portal). |
| `customer_name`, `customer_phone` | Char | Datos de contacto. |
| `party_size` | Integer | Número de personas (default 2). |
| `zone` | Selection (`main`=Interior, `patio`=Patio) | Zona preferida. |
| `table_id` | Many2one `restaurant.table` | Mesa asignada. |
| `start_datetime`, `end_datetime` | Datetime | Ventana de la reserva (duración fija). |
| `state` | Selection | Estado (ver 5.3). |
| `arrangement_product_id` | Many2one `product.template` | Arreglo especial (servicio). |
| `arrangement_type` | Selection | Tipo de arreglo (legado). |
| `arrangement_charged` | Boolean | Evita doble cargo del arreglo en POS. |
| `pre_order_line_ids` | One2many | Líneas de pre-orden. |
| `pre_order_total`, `pre_order_count` | (compute, store) | Totales de la pre-orden. |
| `pre_order_lines_charged` | Boolean | Evita volcar dos veces la pre-orden al POS. |

Constantes: `RESERVATION_MINUTES = 60`, `BUFFER_MINUTES = 15` (la reserva ocupa
la mesa 60 min + 15 de margen).

### 5.3 Estados de `restaurant.table.reservation`

| Valor | Etiqueta | Etiqueta portal |
|-------|----------|-----------------|
| `draft` | Borrador | Pendiente |
| `confirmed` | Confirmada | Confirmada |
| `seated` | Sentados | En curso |
| `done` | Finalizada | Finalizada |
| `cancelled` | Cancelada | Cancelada |

### 5.4 Métodos relevantes

| Método | Propósito |
|--------|-----------|
| `_get_end_datetime(start)` | Calcula el fin = inicio + 75 min. |
| `_get_business_schedule()` | Reutiliza el horario de delivery para validar reservas. |
| `_validate_requested_start_datetime()` | Valida que la hora caiga en el horario operativo y no sea pasada. |
| `_get_time_options(date)` | Genera las horas válidas para una fecha. |
| `_get_available_tables(start, party_size, zone)` | Devuelve mesas libres (sin solapamiento) con capacidad y zona. |
| `_get_arrangement_products()` | Productos de arreglo para el formulario web. |
| `_get_pre_order_products()` | Productos habilitados para pre-orden. |
| `action_confirm()` / `action_seated()` / `action_done()` / `action_cancel()` | Transiciones de estado. |
| `_create_pos_order_for_reservation()` | Crea una orden POS en borrador para la mesa al sentar. |
| `_inject_pre_order_lines_into_pos_order()` | Vuelca las líneas de pre-orden al POS. |
| `_notify_pos_reservation_change()` | Notifica al POS por `bus.bus` (canal snapshot). |
| `_check_reservation_rules()` | Restricciones: capacidad, zona, solapamiento, fin > inicio. |

### 5.5 Integración con POS (en el código)

- `restaurant.table` (heredado) añade `zone` (derivada del nombre del piso:
  "Interior" → `main`, "Patio" → `patio`) y `current_arrangement`.
- Métodos `@api.model` invocados desde el POS:
  - `get_pos_reservation_snapshot()` — estado de reservas activas por mesa.
  - `mark_reservation_charged_for_table(table_id)` — inyecta la línea del arreglo
    en la orden POS en borrador.
  - `finalize_pos_reservation_for_table(table_id)` — finaliza la reserva.
- `pos.order.line` añade `reservation_id` (línea proveniente de la pre-orden) y,
  al eliminarse, registra el ajuste en el chatter de la reserva.
- Canal de bus: `restaurant_table_reservations.snapshot`.
- Assets POS: `static/src/js/pos_reservation_pos.js`, `pos_reservations.css`.

### 5.6 Controladores y rutas web

**`controllers/main.py`** (`http.Controller`):

| Ruta | Método | Auth | Descripción |
|------|--------|------|-------------|
| `/reservas` , `/reservas/mesa` | GET | user | Formulario de reserva (con reprogramación opcional). |
| `/reservas/availability` | GET (json) | user | Disponibilidad de mesas y horas (consulta AJAX). |
| `/reservas/create` | POST | user | Crea y confirma la reserva. |

**`controllers/portal_reservations.py`** (hereda `CustomerPortal`):

| Ruta | Método | Auth | Descripción |
|------|--------|------|-------------|
| `/my/reservations` , `/my/reservations/page/<int:page>` | GET | user | Lista de reservas del cliente. |
| `/my/reservations/<int:reservation_id>` | GET | user | Detalle de una reserva. |
| `/my/reservations/<int:reservation_id>/cancel` | POST | user | Cancela la reserva (si aplica). |

### 5.7 Vistas y datos

- Vistas backend: `restaurant_table_views.xml`, `table_reservation_views.xml`,
  `product_template_views.xml`.
- Vistas web/portal: `reservation_website_templates.xml`, `portal_templates.xml`.
- Datos: `arrangement_products.xml` (productos de arreglo).
- Assets frontend: `reservation.css`, `reservation.js`.
- Assets POS: `pos_reservations.css`, `pos_reservation_pos.js`.

---

## 6. Módulo `pay_kushki` (integración complementaria)

Proveedor de pago externo (autor: *Dainier Escalona*) que añade **Kushki** como
método de pago al flujo de e-commerce. **No** es un módulo principal del
restaurante; se integra por el mecanismo estándar de pagos de Odoo. Detalle del
flujo en [04_integraciones.md](04_integraciones.md).

### 6.1 Modelos heredados

- **`payment.provider`** (`models/payment_provider.py`): añade el código
  `kushki` y campos de credenciales/configuración (`kushki_publicmerchantmd`,
  `kushki_privatemerchantmd`, `kushki_kformid`, `kushki_intestenvironment`,
  `kushki_url`, `kushki_sitedomain`, `kushki_url_otp`). Sobreescribe
  `_get_compatible_providers`, `_get_supported_currencies` (solo USD) y
  `_get_default_payment_method_codes`.
- **`payment.transaction`** (`models/payment_transaction.py`): añade
  `kushki_type`; sobreescribe `_get_specific_rendering_values`,
  `_get_tx_from_notification_data` y `_process_notification_data` para procesar
  la respuesta de Kushki (aprobación / cancelación / error).

### 6.2 Controladores y rutas web

**`controllers/controllers.py`** (`http.Controller`):

| Ruta | Método | Auth | Descripción |
|------|--------|------|-------------|
| `/payment_kushki/paid` | POST | user | Construye y renderiza la "kajita" (formulario de Kushki). |
| `/kushki_confirm` | GET/POST | public | Confirma el pago contra la API de Kushki y procesa la transacción. |

### 6.3 Frontend / datos

- JS: `static/src/js/kushki.js` + script externo
  `https://cdn.kushkipagos.com/kushki-checkout.js` (CDN, cargado como asset
  frontend).
- Vistas: `payment_kushki_templates.xml`, `payment_provider_views.xml`,
  `payment_transaction_views.xml`.
- Datos: `data/payment_provider_data.xml`, `data/neutralize.sql`.
- Constantes (`const.py`): moneda soportada **USD**.

> Las credenciales de Kushki son **sensibles**; ver [SECURITY.md](../SECURITY.md).

---

## 7. Seguridad (resumen técnico)

Cada módulo define `security/ir.model.access.csv` y, donde aplica, reglas de
registro (`security/ir_rule.xml`). Resumen del delivery:

| Modelo | Mesero | Repartidor | Cocinero | Administración | Administrador | Portal |
|--------|--------|-----------|----------|----------------|---------------|--------|
| `restaurant.delivery.order` | RWC | RW | R | RWC | RWCD | R |
| `restaurant.delivery.incident` | RWC | R | R | RWC | RWCD | R |
| `restaurant.delivery.rating` | R | R | R | RWC | RWCD | R + C |
| `restaurant.delivery.schedule*` | — | — | — | RWC | RWCD | R (group_user) |

(R=read, W=write, C=create, D=delete.)

Reservas:

| Modelo | Mesero | Administración | Administrador | Portal |
|--------|--------|----------------|---------------|--------|
| `restaurant.table` | R | RWC | RWCD | R |
| `restaurant.table.reservation` | RWC | RWC | RWCD | R + C |
| `restaurant.table.reservation.line` | RWC | RWC | RWCD | — |

Reglas de registro (`ir.rule`) relevantes:
- Delivery: el **repartidor** solo ve sus pedidos (`driver_id = user.id`); el
  **portal** solo ve los pedidos/incidencias/calificaciones de su
  `commercial_partner_id`.
- Reservas: el **portal** solo ve sus propias reservas.

Además, el modelo `restaurant.delivery.order` refuerza por código las
restricciones del repartidor (no crear, no eliminar, solo cambiar `state`/`notes`
a `on_route`/`delivered`).

---

## 8. Integración con Odoo estándar

- **`sale.order` / `sale.order.line`:** origen de los pedidos de delivery y de la
  facturación; la confirmación de la venta crea/sincroniza el pedido de delivery.
- **`account.move`:** facturas de cliente asociadas, expuestas en el portal de
  delivery.
- **`portal` (`CustomerPortal`):** los controladores de delivery y reservas
  extienden el portal del cliente y sus contadores.
- **`website_sale`:** checkout, programación de entrega y costo fijo de envío.
- **`point_of_sale` / `pos_restaurant`:** integración de reservas con el mapa de
  mesas y las órdenes del POS.
- **`payment` / `website_payment`:** Kushki como proveedor de pago.
- **`mail`:** chatter, plantillas de correo y actividades.
- **`bus.bus`:** notificación en tiempo real al POS de cambios en reservas.

---

## 9. Notas finales

- Los archivos `__pycache__/*.pyc` presentes en el árbol son artefactos
  compilados; no forman parte del código fuente y deberían excluirse del control
  de versiones (ya cubierto por `.gitignore`).
- Algunos métodos utilitarios de migración/configuración están pensados para
  ejecutarse vía `odoo shell` y no se invocan desde la interfaz; su uso operativo
  está **pendiente de validar** según el procedimiento del equipo.
