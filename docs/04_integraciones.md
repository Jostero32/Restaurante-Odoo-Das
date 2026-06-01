# 04 — Integraciones

Este documento describe cómo los módulos del Restaurante Casa Vieja se integran
entre sí y con los módulos estándar de Odoo, así como con la pasarela de pago
Kushki. Solo se documentan integraciones presentes en el código.

---

## 1. Integración con e-commerce / `sale.order`

El módulo `restaurant_delivery_orders` extiende `sale.order` para conectar la
**tienda en línea** con la **operación de delivery**.

### Flujo de datos

```
Cliente compra en /shop
        │
        ▼
   sale.order  ── action_confirm() / write() ──┐
        │                                       │
        │  _sync_delivery_order_from_sale()     │
        ▼                                       │
restaurant.delivery.order  ◄────────────────────┘
        │
        │  action_ensure_invoice() / action_finalize_delivery_invoicing()
        ▼
   account.move (factura de cliente)
```

Puntos clave:
- Al confirmarse una venta candidata a delivery, se crea o actualiza un
  `restaurant.delivery.order` mediante `_sync_delivery_order_from_sale()`.
- En e-commerce, una venta en estado `sent` con líneas reales también se
  considera candidata (`_is_delivery_sync_candidate`).
- Se asegura una **línea técnica de costo de envío** (`is_delivery_fee`) según el
  `delivery_fixed_fee` de la compañía.
- La facturación se gestiona con `action_ensure_invoice()` y
  `action_finalize_delivery_invoicing()` (confirma, factura y envía por correo).
- La **entrega programada** se propaga vía `delivery_is_scheduled` /
  `delivery_scheduled_for`, validada por `_validate_scheduled_delivery_slot()`.

### Horario de entrega en el checkout

Rutas JSON en `website_sale_checkout.py`:

| Ruta | Descripción |
|------|-------------|
| `/shop/delivery_schedule/window` | Devuelve los slots disponibles según el horario de la compañía. |
| `/shop/delivery_schedule/set` | Fija o limpia la entrega programada en el carrito. |

El cálculo de slots usa el modelo `restaurant.delivery.schedule`
(`get_available_slots_window`, `is_open_at`).

---

## 2. Integración con el portal del cliente

Ambos módulos extienden `CustomerPortal` para exponer datos al cliente.

### Delivery (`portal_delivery.py`)
- Contadores en `/my`: `delivery_order_count`, `delivery_invoice_count`.
- Páginas: lista de pedidos, lista y detalle de facturas, detalle de pedido
  (con barra de progreso), formularios de calificación, reorden e incidencia.
- Filtros y ordenamientos para pedidos y facturas.

### Reservas (`portal_reservations.py`)
- Contador en `/my`: `reservation_count`.
- Páginas: lista de reservas, detalle, cancelación.
- Filtros: Todas, Activas, Historial.

> Las reglas de registro (`ir.rule`) garantizan que cada cliente solo vea sus
> propios pedidos, facturas y reservas.

---

## 3. Integración con POS para reservas

El módulo `restaurant_table_reservations` integra las reservas con el **Punto de
Venta** de Odoo (`point_of_sale` / `pos_restaurant`).

### Flujo

```
Reserva confirmada
      │  action_seated()
      ▼
_create_pos_order_for_reservation()      → pos.order (state=draft) para la mesa
      │
_inject_pre_order_lines_into_pos_order() → pos.order.line (reservation_id)
      │
_notify_pos_reservation_change()         → bus.bus (canal snapshot)
      ▼
Interfaz POS (pos_reservation_pos.js) refleja la reserva y el arreglo
```

Métodos invocables desde el POS (sobre `restaurant.table`):
- `get_pos_reservation_snapshot()` — reservas activas por mesa.
- `mark_reservation_charged_for_table(table_id)` — inyecta el cargo del arreglo
  especial en la orden POS en borrador (evita doble cargo con
  `arrangement_charged`).
- `finalize_pos_reservation_for_table(table_id)` — finaliza la reserva.

La **zona** de cada mesa se deriva del nombre del piso del POS ("Interior" →
`main`, "Patio" → `patio`).

### Reutilización del horario
Las reservas **no** tienen su propio modelo de horario: reutilizan
`restaurant.delivery.schedule` mediante `_get_business_schedule()`. Por ello,
`restaurant_table_reservations` depende de `restaurant_delivery_orders`.

---

## 4. Integración de pagos Kushki

`pay_kushki` añade Kushki como **proveedor de pago** al flujo de e-commerce de
Odoo. Es una integración **complementaria**: se apoya en el framework de pagos
estándar (`payment`, `website_sale`, `website_payment`).

### Flujo de pago

```
Checkout (/shop/payment)
      │  Odoo renderiza el proveedor Kushki
      ▼
payment.transaction._get_specific_rendering_values()
      │  prepara datos (credenciales, monto, líneas, cliente)
      ▼
/payment_kushki/paid (POST)  → renderiza la "kajita" (kushki-checkout.js, CDN)
      │  el cliente ingresa los datos de la tarjeta
      ▼
/kushki_confirm  → POST a la API de Kushki (card/v1/charges)
      │
      ├─ ticketNumber presente → _process_notification_data() → _set_done()
      └─ sin ticket            → mensaje de error / _set_canceled()
```

Configuración del proveedor (`payment.provider` heredado):
- `kushki_publicmerchantmd`, `kushki_privatemerchantmd`, `kushki_kformid`
  (credenciales).
- `kushki_intestenvironment` (entorno de prueba, default `True`).
- `kushki_url`, `kushki_url_otp`, `kushki_sitedomain` (endpoints UAT por defecto).
- Moneda soportada: **USD** (`const.SUPPORTED_CURRENCIES`).

> Las URLs por defecto apuntan al entorno **UAT** (pruebas) de Kushki. El uso en
> producción y las credenciales reales están **pendientes de validar** y deben
> configurarse fuera del repositorio (ver [SECURITY.md](../SECURITY.md)).

---

## 5. Resumen de rutas web

### Delivery
| Ruta | Tipo |
|------|------|
| `/my/delivery` | Portal (lista) |
| `/my/delivery/page/<int:page>` | Portal (paginación) |
| `/my/delivery/<int:order_id>` | Portal (detalle) |
| `/my/delivery/<int:order_id>/rate` | POST (calificar) |
| `/my/delivery/<int:order_id>/reorder` | POST (reordenar) |
| `/my/delivery/<int:order_id>/incident` | POST (incidencia) |
| `/my/delivery/invoices` | Portal (facturas) |
| `/my/delivery/invoices/<int:invoice_id>` | Portal (detalle factura) |
| `/shop/delivery_schedule/window` | JSON |
| `/shop/delivery_schedule/set` | JSON |

### Reservas
| Ruta | Tipo |
|------|------|
| `/reservas` , `/reservas/mesa` | Web (formulario) |
| `/reservas/availability` | GET JSON (disponibilidad) |
| `/reservas/create` | POST (crear) |
| `/my/reservations` | Portal (lista) |
| `/my/reservations/<int:reservation_id>` | Portal (detalle) |
| `/my/reservations/<int:reservation_id>/cancel` | POST (cancelar) |

### Kushki
| Ruta | Tipo |
|------|------|
| `/payment_kushki/paid` | POST |
| `/kushki_confirm` | GET/POST |

---

## 6. Flujo de datos entre módulos (visión global)

```
restaurant_casa_vieja_base
   └── grupos + menú raíz  ──► consumidos por delivery y reservas

restaurant_delivery_orders
   ├── sale.order / account.move (ventas y facturas)
   ├── website_sale (checkout, costo de envío, programación)
   ├── portal (/my/delivery)
   └── restaurant.delivery.schedule ──► reutilizado por reservas

restaurant_table_reservations
   ├── restaurant.delivery.schedule (horario, reutilizado)
   ├── point_of_sale / pos_restaurant (mesas, órdenes POS)
   └── portal (/my/reservations)

pay_kushki
   └── payment / website_sale ──► método de pago en el checkout
```

---

## 7. Observaciones técnicas

- La sincronización venta → delivery usa **contextos** (`skip_delivery_sync`,
  `skip_delivery_line_sync`, etc.) para evitar bucles de actualización.
- La integración POS usa `bus.bus` para refrescar la interfaz en tiempo real.
- Kushki opera con un **CDN externo** (`cdn.kushkipagos.com`); su disponibilidad
  depende de la conectividad y debe considerarse en pruebas.

## 8. Limitaciones

- No existe integración con un **módulo de cocina** (no desarrollado).
- El horario de reservas está **acoplado** al de delivery.
- La integración Kushki está configurada por defecto para **UAT**; el flujo
  productivo está **pendiente de validar**.
- El comportamiento exacto de algunos endpoints JSON puede variar según la
  configuración del sitio web y debe verificarse en pruebas (ver
  [06_plan_pruebas.md](06_plan_pruebas.md)).
