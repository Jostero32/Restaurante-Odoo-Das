# 07 — Casos de Prueba Funcionales

Este documento contiene los casos de prueba funcionales del sistema. Están
separados por área: **Reservas**, **Delivery**, **Seguridad/Roles** e
**Integraciones**.

Cada caso incluye: ID, nombre, módulo, precondiciones, pasos, datos de entrada,
resultado esperado, resultado obtenido, estado y evidencia. Los campos
**Resultado obtenido**, **Estado** y **Evidencia** deben completarse durante la
ejecución (`[COMPLETAR]`).

Convención de estado: `Aprobado` / `Fallido` / `Bloqueado` / `No ejecutado`.

---

## A. Reservas (`restaurant_table_reservations`)

### RES-01 — Mostrar formulario de reservas
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Cliente con cuenta de portal autenticado. |
| Pasos | 1. Ingresar a `/reservas`. |
| Datos de entrada | — |
| Resultado esperado | Se muestra el formulario con zonas (Interior/Patio), personas, fecha, hora y selección de mesa. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-02 — Consultar disponibilidad de mesas
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Mesas configuradas en pisos Interior/Patio; horario operativo activo. |
| Pasos | 1. En `/reservas` elegir zona, personas, fecha y hora. 2. Consultar disponibilidad (`/reservas/availability`). |
| Datos de entrada | Zona: Interior; Personas: 2; Fecha: hoy o futura; Hora: dentro del horario. |
| Resultado esperado | Se listan mesas con capacidad ≥ personas y de la zona elegida. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-03 — Crear y confirmar una reserva
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Disponibilidad de mesas para la fecha/hora. |
| Pasos | 1. Completar el formulario. 2. Seleccionar mesa. 3. Enviar (`/reservas/create`). |
| Datos de entrada | Nombre, teléfono, zona, personas, fecha/hora válidas, mesa disponible. |
| Resultado esperado | Reserva creada y confirmada; redirección a `/my/reservations?success=1`. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-04 — Rechazar reserva en horario no operativo
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Existe una excepción de cierre o fecha fuera de horario. |
| Pasos | 1. Elegir una fecha/hora fuera del horario o un día cerrado. 2. Intentar reservar. |
| Datos de entrada | Fecha de un día cerrado / hora fuera de franja. |
| Resultado esperado | Validación que impide la reserva con mensaje claro (cerrado / no opera / no encaja). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-05 — Rechazar reserva con fecha/hora pasada
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | — |
| Pasos | 1. Seleccionar una hora anterior al momento actual. 2. Intentar reservar. |
| Datos de entrada | Fecha/hora en el pasado. |
| Resultado esperado | Error: "No puedes reservar en un horario anterior al momento actual." |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-06 — Validar capacidad de la mesa
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Mesa con capacidad conocida (p. ej. 4 asientos). |
| Pasos | 1. Indicar más personas que la capacidad. 2. Intentar reservar/guardar. |
| Datos de entrada | Personas: 8; Mesa de 4 asientos. |
| Resultado esperado | Validación: la reserva supera la capacidad de la mesa. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-07 — Evitar solapamiento de reservas en la misma mesa
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Existe una reserva activa para una mesa en un horario. |
| Pasos | 1. Intentar reservar la misma mesa en un horario que se solape. |
| Datos de entrada | Misma mesa, horario solapado (dentro de 60+15 min). |
| Resultado esperado | Validación: "Ya existe una reserva activa para esa mesa en el horario indicado." |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-08 — Agregar arreglo especial y pre-orden
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Productos de arreglo y productos de pre-orden configurados. |
| Pasos | 1. En el formulario, elegir un arreglo especial. 2. Agregar productos a la pre-orden. 3. Confirmar. |
| Datos de entrada | Arreglo: "Decoración Cumpleaños"; Pre-orden: 1+ productos. |
| Resultado esperado | Reserva creada con `arrangement_product_id` y líneas de pre-orden; total de pre-orden calculado. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-09 — Reprogramar una reserva
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Reserva en estado Pendiente o Confirmada del propio cliente. |
| Pasos | 1. Desde la reserva, iniciar reprogramación (`/reservas?reschedule_from=<id>`). 2. Cambiar fecha/hora. 3. Confirmar. |
| Datos de entrada | Nueva fecha/hora válida. |
| Resultado esperado | Nueva reserva creada y la anterior cancelada; redirección con `rescheduled=1`. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-10 — Cancelar una reserva desde el portal
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Reserva en estado Pendiente o Confirmada del propio cliente. |
| Pasos | 1. Ir a `/my/reservations/<id>`. 2. Cancelar. |
| Datos de entrada | — |
| Resultado esperado | Reserva pasa a Cancelada; redirección a `/my/reservations?cancelled=1`. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### RES-11 — Impedir cancelación de reserva sentada/finalizada
| Campo | Detalle |
|-------|---------|
| Módulo | Reservas |
| Precondiciones | Reserva en estado Sentados o Finalizada. |
| Pasos | 1. Intentar cancelar la reserva. |
| Datos de entrada | — |
| Resultado esperado | Se impide la cancelación con mensaje de error (estado bloqueado). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

---

## B. Delivery (`restaurant_delivery_orders`)

### DEL-01 — Crear pedido de delivery (backend)
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Usuario Mesero/Administración autenticado. |
| Pasos | 1. Delivery → Pedidos → Crear. 2. Completar datos obligatorios. 3. Guardar. |
| Datos de entrada | Cliente, dirección de entrega, total. |
| Resultado esperado | Pedido creado en estado Recibido con referencia secuencial. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-02 — Confirmar pedido
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Pedido en estado Recibido. |
| Pasos | 1. Abrir el pedido. 2. Pulsar Confirmar. |
| Datos de entrada | — |
| Resultado esperado | Estado pasa a En preparación; se notifica al cliente. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-03 — Asignar repartidor válido
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Pedido confirmado; existe usuario del grupo Repartidor. |
| Pasos | 1. Seleccionar repartidor. 2. Pulsar Asignar. |
| Datos de entrada | Repartidor del grupo Repartidor. |
| Resultado esperado | Estado pasa a Asignado; repartidor queda registrado. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-04 — Rechazar repartidor inválido
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Existe un usuario que NO pertenece al grupo Repartidor (o es Administrador). |
| Pasos | 1. Intentar asignar como repartidor a un usuario no válido. |
| Datos de entrada | Usuario sin rol Repartidor / Administrador. |
| Resultado esperado | Validación que impide la asignación (`_check_driver_role`). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-05 — Transición En camino → Entregado
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Pedido en estado Asignado con repartidor. |
| Pasos | 1. Poner en ruta. 2. Marcar Entregado. |
| Datos de entrada | — |
| Resultado esperado | Estado pasa a En camino y luego a Entregado; se finaliza la facturación de la venta asociada (si existe). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-06 — Impedir cancelación de pedido entregado
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Pedido en estado Entregado. |
| Pasos | 1. Intentar cancelar. |
| Datos de entrada | — |
| Resultado esperado | Error: "No puede cancelar un pedido entregado." |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-07 — Seguimiento del pedido desde el portal
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Cliente con pedidos; autenticado. |
| Pasos | 1. Ir a `/my/delivery`. 2. Abrir un pedido. |
| Datos de entrada | — |
| Resultado esperado | Se muestra la lista y el detalle con barra de progreso y estado simplificado. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-08 — Reportar incidencia
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Pedido del cliente. |
| Pasos | 1. En el detalle, completar tipo y descripción (≥10 caracteres). 2. Enviar. |
| Datos de entrada | Tipo: Demora; Descripción válida. |
| Resultado esperado | Incidencia creada; mensaje en el chatter del pedido; confirmación en el portal. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-09 — Calificar pedido entregado
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Pedido del cliente en estado Entregado, sin calificación previa. |
| Pasos | 1. En el detalle, elegir estrellas (1–5) y comentario. 2. Enviar. |
| Datos de entrada | Score: 5; comentario opcional. |
| Resultado esperado | Calificación registrada; un solo registro por pedido. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### DEL-10 — Programar entrega en el checkout
| Campo | Detalle |
|-------|---------|
| Módulo | Delivery |
| Precondiciones | Horario de delivery con franjas activas; carrito con productos. |
| Pasos | 1. En el checkout, abrir la selección de horario (`/shop/delivery_schedule/window`). 2. Elegir un slot (`/shop/delivery_schedule/set`). |
| Datos de entrada | Slot dentro del horario. |
| Resultado esperado | El carrito queda con entrega programada; al confirmar, el pedido refleja `is_scheduled`. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

---

## C. Seguridad / Roles (`restaurant_casa_vieja_base` + reglas)

### SEG-01 — Repartidor solo ve sus pedidos
| Campo | Detalle |
|-------|---------|
| Módulo | Seguridad |
| Precondiciones | Dos pedidos: uno asignado al repartidor, otro no. |
| Pasos | 1. Iniciar sesión como Repartidor. 2. Listar pedidos. |
| Datos de entrada | — |
| Resultado esperado | Solo ve los pedidos donde `driver_id` es él (regla `ir.rule`). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### SEG-02 — Repartidor no puede crear ni eliminar pedidos
| Campo | Detalle |
|-------|---------|
| Módulo | Seguridad |
| Precondiciones | Sesión como Repartidor. |
| Pasos | 1. Intentar crear un pedido. 2. Intentar eliminar uno. |
| Datos de entrada | — |
| Resultado esperado | Acceso denegado (no create, no unlink); solo puede cambiar estado a En camino/Entregado y notas. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### SEG-03 — Mesero no puede eliminar registros
| Campo | Detalle |
|-------|---------|
| Módulo | Seguridad |
| Precondiciones | Sesión como Mesero. |
| Pasos | 1. Intentar eliminar una reserva o pedido. |
| Datos de entrada | — |
| Resultado esperado | Acción de eliminación no disponible/denegada (perm_unlink = 0). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### SEG-04 — Cliente de portal solo ve sus datos
| Campo | Detalle |
|-------|---------|
| Módulo | Seguridad |
| Precondiciones | Dos clientes con pedidos/reservas distintos. |
| Pasos | 1. Iniciar sesión como cliente A. 2. Intentar acceder a pedidos/reservas de B (cambiando el ID en la URL). |
| Datos de entrada | ID de un registro ajeno. |
| Resultado esperado | El cliente A no accede a los datos de B (redirección/denegación por `ir.rule`). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### SEG-05 — Administrador con control total
| Campo | Detalle |
|-------|---------|
| Módulo | Seguridad |
| Precondiciones | Sesión como Administrador Restaurante. |
| Pasos | 1. Crear, editar y eliminar un pedido y una reserva de prueba. |
| Datos de entrada | — |
| Resultado esperado | Todas las operaciones CRUD son posibles. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

---

## D. Integraciones

### INT-01 — Sincronización venta → pedido de delivery
| Campo | Detalle |
|-------|---------|
| Módulo | Integración (sale.order ↔ delivery) |
| Precondiciones | Venta de e-commerce con líneas reales. |
| Pasos | 1. Confirmar la venta. 2. Verificar el pedido de delivery generado. |
| Datos de entrada | Venta con cliente y productos. |
| Resultado esperado | Se crea/actualiza un `restaurant.delivery.order` enlazado (`sale_order_id`); se asegura la factura. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### INT-02 — Reserva sentada genera orden POS con pre-orden
| Campo | Detalle |
|-------|---------|
| Módulo | Integración (reservas ↔ POS) |
| Precondiciones | Sesión POS abierta; reserva confirmada con pre-orden. |
| Pasos | 1. Marcar la reserva como Sentados. 2. Revisar la orden POS de la mesa. |
| Datos de entrada | Reserva con líneas de pre-orden. |
| Resultado esperado | Se crea una orden POS en borrador para la mesa y se vuelcan las líneas de pre-orden (`reservation_id`). |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

### INT-03 — Pago con Kushki (entorno de prueba)
| Campo | Detalle |
|-------|---------|
| Módulo | Integración (pago Kushki) |
| Precondiciones | Proveedor Kushki configurado en UAT; conectividad al CDN. |
| Pasos | 1. En el checkout, elegir Kushki. 2. Completar la "kajita". 3. Confirmar. |
| Datos de entrada | Tarjeta de prueba de Kushki (UAT). |
| Resultado esperado | La transacción se procesa; con `ticketNumber` se marca como pagada (`_set_done`), en caso contrario error/cancelada. |
| Resultado obtenido | `[COMPLETAR]` |
| Estado | `[COMPLETAR]` |
| Evidencia | `[COMPLETAR]` |

---

> **Nota:** los resultados esperados se derivan del comportamiento implementado
> en el código (validaciones, estados y reglas de seguridad). El comportamiento
> exacto de la interfaz web puede requerir ajustes menores y está *pendiente de
> validar* durante la ejecución real.
