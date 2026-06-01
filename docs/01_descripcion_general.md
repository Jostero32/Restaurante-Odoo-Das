# 01 — Descripción General del Sistema

## 1. Presentación

**Restaurante Casa Vieja** es un sistema de gestión construido sobre **Odoo 18**
y desplegado mediante **Docker Compose**. El sistema digitaliza dos canales de
atención del restaurante —**pedidos a domicilio (delivery)** y **reservas de
mesa**— y los integra con los módulos estándar de Odoo (ventas, facturación,
portal del cliente, Punto de Venta y pagos en línea).

El desarrollo está organizado en módulos personalizados ubicados en la carpeta
`addons/`, sobre una base común que define los roles y el menú del restaurante.

## 2. Problema que resuelve

El restaurante necesita:

- Recibir y **gestionar pedidos a domicilio** originados en su tienda en línea,
  con seguimiento del estado, asignación de repartidores, manejo de incidencias,
  calificación del servicio y facturación.
- Permitir a los clientes **reservar mesas** por la web, eligiendo zona, mesa,
  horario y, opcionalmente, arreglos especiales (decoración) y una pre-orden de
  productos.
- Reflejar las reservas en el **Punto de Venta (POS)** para que el personal de
  salón pueda atender la mesa con la información preparada de antemano.
- Ofrecer un **canal de pago digital** (Kushki) dentro del flujo de compra en
  línea.

Antes de esta solución, estos procesos serían manuales o estarían dispersos en
herramientas separadas. El sistema los unifica sobre una sola plataforma.

## 3. Objetivo general

Proveer una plataforma integral que centralice la operación de delivery y
reservas del Restaurante Casa Vieja, reutilizando la infraestructura de Odoo 18,
con seguimiento para el cliente desde el portal y control operativo para el
personal según su rol.

## 4. Alcance funcional

El sistema cubre, según lo implementado en el código:

### Pedidos a domicilio (delivery)
- Registro de pedidos manualmente o automáticamente desde una venta de
  e-commerce (`sale.order`).
- Estados operativos: Recibido, En preparación, Asignado, En camino, Entregado,
  Cancelado.
- Asignación de repartidores con validación de rol.
- Incidencias del pedido (tipo, descripción, estado de resolución).
- Calificación del cliente (1 a 5 estrellas) sobre pedidos entregados.
- Horarios de entrega configurables (franjas semanales y excepciones/feriados),
  con entrega programada por el cliente en el checkout.
- Costo fijo de envío configurable por compañía.
- Facturación asociada y seguimiento de facturas desde el portal.
- Notificaciones por correo y por chat del portal ante cambios de estado.

### Reservas de mesa
- Formulario web para crear reservas eligiendo zona (Interior / Patio), número
  de personas, fecha y hora, mesa disponible y arreglo especial opcional.
- Pre-orden de productos habilitados para reserva.
- Validaciones de horario operativo, capacidad de mesa, zona y solapamiento.
- Estados: Borrador, Confirmada, Sentados, Finalizada, Cancelada.
- Integración con el POS de Odoo: creación de orden POS en borrador al sentar,
  volcado de la pre-orden y cobro del arreglo especial.
- Portal del cliente para consultar, reprogramar y cancelar reservas.

### Pagos (integración complementaria)
- Proveedor de pago **Kushki** para el flujo de e-commerce, que permite el pago
  con tarjeta dentro de la tienda en línea.

## 5. Arquitectura general

El sistema sigue la arquitectura modular de Odoo, contenedorizada con Docker:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Host (Docker)                             │
│                                                                   │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────────────┐     │
│  │   db       │   │   restore    │   │        odoo          │     │
│  │ PostgreSQL │◄──│ (one-shot)   │   │   Odoo 18 :8069      │     │
│  │   15       │   │ restaura BD  │   │   expuesto en :8071  │     │
│  └────────────┘   │ + filestore  │   │                      │     │
│        ▲          └──────────────┘   │  addons/ montados:   │     │
│        │                             │  - base              │     │
│  ┌────────────┐                      │  - delivery_orders   │     │
│  │   backup   │ (perfil tools)       │  - table_reservations│     │
│  │ pg_dump +  │                      │  - pay_kushki        │     │
│  │ filestore  │                      └──────────────────────┘     │
│  └────────────┘                                                   │
│                                                                   │
│  Volúmenes: odoo-db-data, odoo-web-data | Bind: ./addons ./backups│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                   Navegador del cliente / personal
                   (Backend Odoo + Portal + Tienda web)
```

- **Capa de datos:** PostgreSQL 15.
- **Capa de aplicación:** Odoo 18 con los módulos personalizados montados desde
  `./addons`.
- **Capa de presentación:** backend de Odoo (personal), portal y tienda web
  (clientes), y la interfaz del POS (salón).

## 6. Servicios Docker

| Servicio  | Imagen        | Rol |
|-----------|---------------|-----|
| `db`      | `postgres:15` | Motor de base de datos. Expone healthcheck y volumen de datos. |
| `restore` | `postgres:15` | Servicio de un solo uso: restaura `db_demo.dump` y el filestore antes de iniciar Odoo. |
| `odoo`    | `odoo:18`     | Instancia de Odoo. Puerto host `8071` → contenedor `8069`. Arranca actualizando `restaurant_table_reservations`. |
| `backup`  | `postgres:15` | Servicio auxiliar (perfil `tools`) para generar respaldos de base y filestore. |

La base de datos utilizada es `odoo`. Detalles de operación en
[05_instalacion_docker.md](05_instalacion_docker.md).

## 7. Módulos personalizados

| Módulo | Tipo | Descripción breve |
|--------|------|-------------------|
| `restaurant_casa_vieja_base` | Base | Define la categoría de seguridad, los cinco grupos de roles y el menú raíz "Restaurante Casa Vieja". Es la base común de los demás módulos. |
| `restaurant_delivery_orders` | Principal | Gestión completa de pedidos a domicilio, integrada con e-commerce, ventas, facturación y portal. |
| `restaurant_table_reservations` | Principal | Gestión de reservas de mesa, con portal web e integración con el POS. |
| `pay_kushki` | Integración | Proveedor de pago Kushki para el flujo de e-commerce (autor externo). |

## 8. Roles de usuario

Los roles se definen como grupos de seguridad en el módulo base:

| Rol | Descripción | Capacidad principal |
|-----|-------------|---------------------|
| **Repartidor Restaurante** | Personal de reparto a domicilio. | Lee sus pedidos asignados y actualiza su estado (a "En camino" / "Entregado"). |
| **Cocinero Restaurante** | Personal de cocina. | Solo lectura sobre los modelos operativos. *(No existe aún un módulo de cocina; ver Mejoras futuras.)* |
| **Mesero Restaurante** | Personal de salón. | Toma reservas y pedidos; no elimina. |
| **Administración Restaurante** | Coordinación operativa. | Crea y edita todos los registros; no elimina. Hereda Mesero y Cocinero. |
| **Administrador Restaurante** | Control total. | CRUD completo sobre los modelos del sistema. |

Además, intervienen los roles estándar de Odoo: **Portal** (clientes con cuenta)
y **Público** (visitantes), que acceden a la tienda y al portal con permisos
restringidos por reglas de registro.

## 9. Flujo general del negocio

### Delivery
1. El cliente compra en la tienda en línea (`/shop`). Opcionalmente paga con
   Kushki y puede **programar** la hora de entrega.
2. Al confirmarse la venta, se sincroniza un **pedido de delivery**
   (`restaurant.delivery.order`) y se asegura la factura.
3. El personal gestiona el pedido: confirma, asigna repartidor, lo pone en ruta.
4. El **repartidor** marca "En camino" y "Entregado".
5. El cliente sigue el pedido desde **`/my/delivery`**, puede reportar
   incidencias, **calificar** y **reordenar**.

### Reservas
1. El cliente abre **`/reservas`**, elige zona, personas, fecha/hora y consulta
   disponibilidad.
2. Selecciona una mesa disponible, opcionalmente un **arreglo especial** y una
   **pre-orden** de productos, y confirma.
3. Se crea la reserva (`restaurant.table.reservation`) y se notifica al personal
   de salón.
4. El **mesero/administración** confirma y, al llegar el cliente, marca
   **"Sentados"**: se crea una orden POS en borrador, se vuelca la pre-orden y
   se puede cobrar el arreglo.
5. El cliente consulta, reprograma o cancela desde **`/my/reservations`**.

## 10. Limitaciones actuales

- **No existe un módulo de cocina** (tablero Kanban de preparación, pantalla de
  mesero dedicada). El grupo "Cocinero" existe, pero su alcance se limita a
  lectura sobre los modelos operativos.
- La integración con Kushki opera principalmente en **entorno de prueba** (UAT)
  según la configuración por defecto del proveedor; su uso en producción está
  **pendiente de validar**.
- El horario operativo de reservas **reutiliza** el horario configurado para
  delivery (`restaurant.delivery.schedule`); no existe un horario independiente
  para reservas.
- La experiencia responsive y de accesibilidad puede requerir mejoras
  (pendiente de validar con pruebas en distintos dispositivos).
- No hay automatización de pruebas ni pipeline de CI/CD en el repositorio.

## 11. Mejoras futuras

- **Módulo de cocina** (mejora futura, no desarrollada):
  - Tablero **Kanban de cocina** para seguimiento de la preparación de pedidos.
  - **Pantalla de mesero** dedicada para gestión de salón.
- **Mejora responsive** de los formularios web (reservas y delivery).
- **Automatización de pruebas** funcionales y de regresión.
- **Pipeline CI/CD** para integración y despliegue continuos.
- Horario operativo **independiente** para reservas (desacoplado de delivery).
- Validación y endurecimiento de la integración Kushki para producción.

> Estas mejoras se detallan en
> [09_hallazgos_mejoras.md](09_hallazgos_mejoras.md).
