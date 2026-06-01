# Evidencias

Esta carpeta almacena las **capturas de pantalla** y evidencias que respaldan la
documentación, el plan de pruebas y los resultados de rendimiento del sistema
**Restaurante Casa Vieja**.

---

## 1. Cómo nombrar las capturas

Use una nomenclatura **ordenada, descriptiva y en minúsculas**, con el formato:

```
<NN>_<area>_<descripcion>.png
```

Donde:
- `NN` = número de dos dígitos para ordenar (`01`, `02`, …).
- `area` = área o módulo (`docker`, `odoo`, `delivery`, `reservas`, `pos`,
  `kushki`, `jmeter`, `seguridad`).
- `descripcion` = breve descripción en `snake_case`.

Reglas:
- Formato preferido: **PNG** (también se acepta JPG).
- Sin espacios ni tildes en el nombre del archivo.
- Una imagen por evidencia; recortar lo relevante.
- Si una evidencia corresponde a un caso de prueba, referencie su **ID** en el
  documento correspondiente (p. ej. `RES-03`, `DEL-09`).

---

## 2. Capturas requeridas

### Entorno (Docker / Odoo)
- `01_docker_compose_ps.png` — salida de `docker compose ps` con los servicios
  arriba.
- `02_odoo_login.png` — pantalla de inicio de sesión de Odoo.
- `03_menu_restaurante.png` — menú raíz "Restaurante Casa Vieja" en el backend.

### Delivery
- `04_delivery_pedido_backend.png` — formulario de un pedido de delivery con los
  botones de estado.
- `05_delivery_portal_lista.png` — lista de pedidos del cliente en `/my/delivery`.
- `06_delivery_portal_detalle.png` — detalle de un pedido con la barra de
  progreso.
- `07_delivery_incidencia.png` — formulario/registro de una incidencia.
- `08_delivery_calificacion.png` — calificación de un pedido entregado.
- `09_delivery_checkout_horario.png` — selección de horario de entrega en el
  checkout *(si aplica)*.

### Reservas
- `10_reservas_formulario.png` — formulario de reserva en `/reservas`.
- `11_reservas_disponibilidad.png` — mesas disponibles tras consultar
  disponibilidad.
- `12_reservas_arreglo_preorden.png` — selección de arreglo especial y pre-orden.
- `13_reservas_portal_lista.png` — lista de reservas del cliente en
  `/my/reservations`.
- `14_reservas_portal_detalle.png` — detalle de una reserva.

### POS (si aplica)
- `15_pos_mesa_reservada.png` — mapa de mesas del POS con una mesa reservada.
- `16_pos_preorden_volcada.png` — orden POS con las líneas de pre-orden de la
  reserva.

### Kushki (si aplica)
- `17_kushki_proveedor.png` — configuración del proveedor de pago Kushki
  (entorno de prueba).
- `18_kushki_checkout.png` — "kajita" / formulario de pago en el checkout.
- `19_kushki_resultado.png` — pantalla de resultado de la transacción.

### Seguridad / Roles
- `20_seguridad_repartidor_vista.png` — vista del repartidor con solo sus
  pedidos.
- `21_seguridad_portal_acceso_denegado.png` — intento de acceso a datos ajenos
  denegado.

### JMeter (rendimiento)
- `22_jmeter_thread_group.png` — configuración del Thread Group (10 usuarios,
  ramp-up 10s, 5 iteraciones).
- `23_jmeter_summary_reservas.png` — Summary Report del escenario `GET /reservas`.
- `24_jmeter_summary_availability.png` — Summary Report del escenario
  `GET /reservas/availability`.
- `25_jmeter_aggregate.png` — Aggregate Report comparativo.
- `26_jmeter_grafico.png` — gráfico de tiempos de respuesta.

---

## 3. Notas

- Las capturas marcadas como *(si aplica)* dependen de que la funcionalidad o
  integración esté disponible y configurada en el entorno de pruebas.
- Los documentos en `docs/` contienen marcadores
  `[CAPTURA PENDIENTE: ...]` que indican dónde se referencia cada evidencia.
- No incluir en las capturas **credenciales reales**, tokens ni datos personales
  sensibles (difuminarlos si fuese necesario).
