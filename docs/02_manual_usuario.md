# 02 — Manual de Usuario

Este manual está dirigido a **usuarios no técnicos**: personal del restaurante
(meseros, repartidores, administración) y clientes que usan la web. Explica de
forma sencilla cómo acceder y usar las funciones del sistema.

> Los marcadores `[CAPTURA PENDIENTE: ...]` indican dónde insertar una imagen de
> apoyo. Las capturas deben guardarse en [evidencias/](evidencias/) siguiendo la
> nomenclatura indicada en su `README.md`.

---

## 1. Acceso al sistema

El sistema tiene tres formas de uso según quién lo utilice:

| Quién | Dónde | Cómo |
|-------|-------|------|
| Personal del restaurante | **Backend de Odoo** | `http://<servidor>:8071`, iniciando sesión con usuario y contraseña. |
| Clientes con cuenta | **Portal** y **Tienda web** | `http://<servidor>:8071/my` y `/shop`. |
| Visitantes | **Tienda web** | `http://<servidor>:8071/shop`. |

> En desarrollo local, el servidor suele ser `http://localhost:8071`.

Para iniciar sesión:

1. Abra la dirección del sistema en el navegador.
2. Ingrese su correo/usuario y contraseña.
3. Presione **Iniciar sesión**.

[CAPTURA PENDIENTE: pantalla de inicio de sesión de Odoo]

---

## 2. Roles y qué puede hacer cada uno

| Rol | Qué puede hacer |
|-----|-----------------|
| **Repartidor** | Ver los pedidos a domicilio que le fueron asignados y actualizar su estado a "En camino" y "Entregado". |
| **Cocinero** | Consultar (solo lectura) la información operativa. |
| **Mesero** | Registrar y gestionar reservas y pedidos; confirmar reservas y sentar clientes. |
| **Administración** | Crear y editar pedidos, reservas, horarios y configuración. |
| **Administrador** | Acceso total, incluida la eliminación de registros. |
| **Cliente (portal)** | Realizar pedidos y reservas desde la web y darles seguimiento. |

[CAPTURA PENDIENTE: menú principal "Restaurante Casa Vieja" en el backend]

---

## 3. Uso de pedidos a domicilio (Delivery)

### 3.1 Para el cliente

#### Realizar un pedido
1. Ingrese a la **tienda en línea** (`/shop`).
2. Agregue productos al carrito y proceda al **pago**.
3. En el checkout puede, si está disponible, **programar la hora de entrega**
   eligiendo un horario entre los ofrecidos.
4. Complete sus datos de entrega y confirme. Si paga con tarjeta, podrá usar
   **Kushki** como método de pago.

[CAPTURA PENDIENTE: checkout de la tienda con opción de horario de entrega]

#### Seguir un pedido
1. Ingrese a **Mi cuenta** → **Mis pedidos de delivery** (`/my/delivery`).
2. Verá la lista de sus pedidos con su estado y un buscador para filtrar
   (En preparación, En camino, Entregados, Con incidencias).
3. Haga clic en un pedido para ver el **detalle** y la **línea de progreso**.

[CAPTURA PENDIENTE: lista de pedidos del cliente en /my/delivery]
[CAPTURA PENDIENTE: detalle de un pedido con la barra de progreso]

#### Reportar una incidencia
En el detalle del pedido, en la sección de incidencias, elija el **tipo**
(pedido incompleto, producto frío, demora, producto incorrecto, otro), escriba
una **descripción** (mínimo 10 caracteres) y envíela.

[CAPTURA PENDIENTE: formulario de incidencia en el detalle del pedido]

#### Calificar un pedido
Cuando el pedido está **Entregado**, en su detalle aparece la opción de
**calificación** (1 a 5 estrellas) con un comentario opcional. Cada pedido se
califica una sola vez.

[CAPTURA PENDIENTE: sección de calificación del pedido entregado]

#### Volver a pedir (reordenar)
Desde un pedido entregado o cancelado, puede usar **"Volver a pedir"** para
cargar los mismos productos en un nuevo carrito.

### 3.2 Para el personal

1. Ingrese al backend y abra **Restaurante Casa Vieja → Delivery → Pedidos**.
2. Seleccione un pedido y use los botones de acción según su rol:
   - **Confirmar** (pasa a "En preparación").
   - **Asignar** (requiere elegir un repartidor válido).
   - **Poner en ruta**.
   - **Entregado**.
   - **Cancelar**.
3. El **repartidor** ve sus pedidos en **Delivery → Mis pedidos** y solo puede
   marcar "En camino" y "Entregado".

[CAPTURA PENDIENTE: formulario de pedido de delivery en el backend con botones de estado]

#### Estados de un pedido de delivery

| Estado | Significado |
|--------|-------------|
| Recibido | Pedido registrado, aún sin confirmar. |
| En preparación | Pedido confirmado, en alistamiento. |
| Asignado | Repartidor asignado. |
| En camino | El repartidor salió a entregar. |
| Entregado | Pedido entregado al cliente. |
| Cancelado | Pedido anulado. |

> Para el cliente, algunos estados internos se muestran de forma simplificada
> (por ejemplo, "Recibido", "En preparación", "En camino", "Entregado").

---

## 4. Uso de reservas de mesa

### 4.1 Para el cliente

#### Crear una reserva
1. Ingrese a **`/reservas`**.
2. Elija la **zona** (Interior o Patio), el **número de personas**, la **fecha**
   y la **hora**. El sistema solo ofrece horarios válidos según el horario del
   restaurante.
3. Pulse para **consultar disponibilidad**: se mostrarán las **mesas
   disponibles** que cumplen la capacidad y la zona.
4. Seleccione una mesa.
5. Opcionalmente, elija un **arreglo especial** (decoración) y agregue una
   **pre-orden** de productos.
6. Complete su nombre y teléfono y **confirme** la reserva.

[CAPTURA PENDIENTE: formulario de reserva en /reservas con mesas disponibles]
[CAPTURA PENDIENTE: selección de arreglo especial y pre-orden]

#### Seguir, reprogramar o cancelar una reserva
1. Ingrese a **Mi cuenta → Mis reservas** (`/my/reservations`).
2. Verá sus reservas con su estado y filtros (Activas, Historial).
3. Desde el detalle puede **reprogramar** (crea una nueva reserva y cancela la
   anterior) o **cancelar** (solo si está en estado Pendiente o Confirmada).

[CAPTURA PENDIENTE: lista de reservas del cliente en /my/reservations]
[CAPTURA PENDIENTE: detalle de una reserva con opción de cancelar]

### 4.2 Para el personal

1. En el backend, abra **Restaurante Casa Vieja → Reservas → Reservas**.
2. Gestione la reserva con los botones de acción:
   - **Confirmar** (Borrador → Confirmada).
   - **Sentar** (Confirmada → Sentados): genera la orden en el POS y vuelca la
     pre-orden.
   - **Finalizar** (Sentados → Finalizada).
   - **Cancelar** (no permitido si ya está Sentada o Finalizada).
3. En el **POS**, la mesa reservada aparece con la información de la reserva y el
   arreglo especial asociado.

[CAPTURA PENDIENTE: formulario de reserva en el backend]
[CAPTURA PENDIENTE: vista del POS con la mesa reservada]

#### Estados de una reserva

| Estado | Significado |
|--------|-------------|
| Borrador / Pendiente | Reserva creada, aún sin confirmar. |
| Confirmada | Reserva aceptada. |
| Sentados | El cliente llegó y está en la mesa (orden POS creada). |
| Finalizada | La atención concluyó. |
| Cancelada | Reserva anulada. |

---

## 5. Seguimiento desde el portal

El **portal del cliente** (`/my`) reúne los accesos a:

- **Mis pedidos de delivery** y **Mis facturas de delivery**.
- **Mis reservas**.

Desde allí el cliente consulta el estado, descarga facturas (delivery), reporta
incidencias, califica y gestiona sus reservas, sin necesidad de contactar al
restaurante.

[CAPTURA PENDIENTE: página principal del portal /my con contadores]

---

## 6. Incidencias y calificaciones

- **Incidencias:** disponibles en el detalle del pedido de delivery. Permiten al
  cliente informar problemas. El personal las revisa y cambia su estado
  (Nueva → En revisión → Resuelta / No procede).
- **Calificaciones:** disponibles en pedidos entregados. El cliente otorga de 1 a
  5 estrellas y un comentario. La calificación queda asociada al repartidor.

---

## 7. Errores comunes y recomendaciones

| Situación | Causa probable | Recomendación |
|-----------|----------------|---------------|
| No aparecen horarios al reservar | El restaurante no opera ese día o la fecha es pasada. | Elija otra fecha/hora dentro del horario de atención. |
| No hay mesas disponibles | Capacidad insuficiente o todas reservadas en ese horario. | Reduzca el número de personas, cambie de zona o de horario. |
| No puedo cancelar mi reserva | La reserva ya está "Sentados" o "Finalizada". | Solo se cancelan reservas Pendientes o Confirmadas. |
| No puedo calificar mi pedido | El pedido aún no está "Entregado" o ya fue calificado. | Espere a que esté entregado; cada pedido se califica una vez. |
| El repartidor no puede confirmar/asignar | Esas acciones no corresponden a su rol. | El repartidor solo marca "En camino" y "Entregado". |
| La incidencia no se envía | La descripción tiene menos de 10 caracteres o falta el tipo. | Complete el tipo y una descripción más detallada. |

### Recomendaciones generales
- Use un navegador actualizado.
- Mantenga sus datos de contacto correctos para recibir notificaciones.
- Ante cualquier duda operativa, el personal puede consultar la
  [documentación técnica](03_documentacion_tecnica.md).

> Algunos comportamientos exactos de la interfaz pueden variar según
> configuración del sitio y están **pendientes de validar** con capturas reales.
