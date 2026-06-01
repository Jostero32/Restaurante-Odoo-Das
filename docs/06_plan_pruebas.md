# 06 — Plan de Pruebas

## 1. Objetivo del plan de pruebas

Definir la estrategia, el alcance, los recursos y los criterios para verificar
que el sistema **Restaurante Casa Vieja (Odoo 18)** cumple con las
funcionalidades implementadas en sus módulos de delivery, reservas e integración
de pagos, así como con las reglas de seguridad por rol y un nivel de rendimiento
aceptable en las rutas web públicas.

## 2. Alcance

### Incluido
- Funcionalidades del módulo **delivery** (`restaurant_delivery_orders`).
- Funcionalidades del módulo **reservas** (`restaurant_table_reservations`).
- **Roles y seguridad** definidos en `restaurant_casa_vieja_base`.
- Integraciones: portal del cliente, `sale.order`/facturación, POS (reservas) y
  pago Kushki (en entorno de prueba).
- **Rendimiento** de rutas web de reservas (ver
  [08_prueba_rendimiento_jmeter.md](08_prueba_rendimiento_jmeter.md)).

### Excluido
- Módulo de **cocina** (no desarrollado).
- Pruebas de carga sobre la pasarela real de Kushki en producción.
- Pruebas de seguridad ofensivas (pentesting) más allá de la verificación de
  permisos por rol.

## 3. Funcionalidades a evaluar

| Área | Funcionalidades |
|------|-----------------|
| Delivery | Creación de pedido (manual y desde e-commerce), transiciones de estado, asignación de repartidor, incidencias, calificación, reorden, horarios/entrega programada, facturación, portal. |
| Reservas | Disponibilidad de mesas, validación de horario y capacidad, creación/confirmación, sentar (integración POS), pre-orden, arreglos especiales, reprogramación, cancelación, portal. |
| Seguridad/Roles | Permisos de Repartidor, Cocinero, Mesero, Administración, Administrador y Portal; reglas de registro (datos propios). |
| Integraciones | Sincronización venta→delivery, factura en portal, POS (snapshot, cargo de arreglo), pago Kushki (UAT). |

## 4. Tipos de pruebas

| Tipo | Descripción |
|------|-------------|
| **Funcionales** | Verifican que cada funcionalidad produce el resultado esperado (ver [07_casos_prueba_funcionales.md](07_casos_prueba_funcionales.md)). |
| **Roles / Seguridad** | Verifican que cada rol solo puede realizar las acciones permitidas y ver sus propios datos. |
| **Rendimiento** | Miden tiempos de respuesta y throughput de rutas web bajo concurrencia (JMeter). |

## 5. Herramientas

| Herramienta | Uso |
|-------------|-----|
| **Odoo 18** | Sistema bajo prueba (backend, portal, POS). |
| **Navegador web** | Ejecución de pruebas funcionales y de portal (Chrome/Firefox actualizado). |
| **Docker / Docker Compose** | Levantar y restaurar el entorno de pruebas. |
| **Apache JMeter** | Pruebas de rendimiento sobre rutas web. |
| **DevTools del navegador** | Inspección de peticiones, tiempos y errores. |

## 6. Entorno de pruebas

- Despliegue local con Docker Compose (ver
  [05_instalacion_docker.md](05_instalacion_docker.md)).
- Base de datos `odoo` restaurada desde `backups/db_demo.dump`.
- Acceso en `http://localhost:8071`.
- Datos de demostración cargados (mesas, productos, horarios).
- Proveedor Kushki configurado en **entorno de prueba (UAT)**.

> El entorno de pruebas debe ser **independiente** de cualquier entorno
> productivo. No usar credenciales reales de Kushki.

## 7. Datos de prueba necesarios

- **Usuarios** por rol: un repartidor, un mesero, un usuario de administración,
  un administrador y al menos un cliente con cuenta de **portal**.
- **Mesas** configuradas en pisos "Interior" y "Patio" del POS.
- **Productos**: al menos uno publicado para la tienda, uno marcado como
  disponible para **pre-orden** de reserva, y los productos de **arreglo
  especial** (categoría "Arreglos de Mesa").
- **Horario de delivery** con franjas activas y, opcionalmente, una excepción
  (feriado) para probar cierres.
- **Sesión POS** abierta para las pruebas de integración de reservas.
- Una **venta de e-commerce** de ejemplo para validar la sincronización a
  delivery y la facturación.

## 8. Responsables

| Actividad | Responsable | Rol |
|-----------|-------------|-----|
| Diseño de casos de prueba | `[COMPLETAR]` | `[COMPLETAR]` |
| Ejecución de pruebas funcionales | `[COMPLETAR]` | `[COMPLETAR]` |
| Ejecución de pruebas de roles/seguridad | `[COMPLETAR]` | `[COMPLETAR]` |
| Ejecución de pruebas de rendimiento (JMeter) | `[COMPLETAR]` | `[COMPLETAR]` |
| Registro de evidencias | `[COMPLETAR]` | `[COMPLETAR]` |
| Revisión y aprobación | `[COMPLETAR]` | `[COMPLETAR]` |

## 9. Criterios de aceptación

Una funcionalidad se considera **aprobada** cuando:
- El resultado obtenido coincide con el **resultado esperado** del caso de prueba.
- No se producen errores no controlados (trazas, *500*, etc.).
- Las **reglas de seguridad** se respetan (cada rol y cada cliente solo accede a
  lo permitido).
- Las validaciones de negocio (capacidad, horario, solapamiento, estados)
  funcionan según lo documentado.

Criterio global: se considera aprobada la fase de pruebas cuando **≥ 95 %** de
los casos funcionales están en estado *Aprobado* y **no existen** defectos de
severidad **Alta** abiertos en seguridad.

## 10. Criterios de suspensión

Las pruebas se **suspenden** si:
- El entorno no levanta o el `restore` falla (bloqueo total).
- Se detecta un defecto **bloqueante** que impide ejecutar la mayoría de los
  casos (por ejemplo, no se pueden crear reservas ni pedidos).
- Se encuentra una **falla de seguridad crítica** (un rol accede a datos o
  acciones que no le corresponden) que invalida el resto de las pruebas hasta su
  corrección.

Se **reanudan** cuando el defecto bloqueante ha sido corregido y verificado.

## 11. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Datos de demo insuficientes (sin mesas/productos) | No se pueden ejecutar casos | Preparar y verificar los datos de prueba antes de iniciar. |
| Sesión POS no abierta | Fallan pruebas de integración de reservas | Abrir sesión POS como precondición. |
| Dependencia del CDN de Kushki | Falla el flujo de pago en pruebas | Verificar conectividad; documentar como *pendiente de validar* si no está disponible. |
| Diferencias de zona horaria | Horarios/slots inconsistentes | Verificar la `tz` de la compañía/usuario. |
| Cacheo de assets web | Comportamiento visual inconsistente | Limpiar assets / actualizar módulo. |
| Entorno compartido con producción | Riesgo de afectar datos reales | Usar entorno aislado exclusivo de pruebas. |

## 12. Evidencias esperadas

- Capturas de pantalla de cada caso ejecutado (ver
  [evidencias/README.md](evidencias/README.md)).
- Tabla de casos de prueba con resultado obtenido y estado
  ([07_casos_prueba_funcionales.md](07_casos_prueba_funcionales.md)).
- Reportes de JMeter (resumen y gráficos) y la tabla de métricas
  ([08_prueba_rendimiento_jmeter.md](08_prueba_rendimiento_jmeter.md)).
- Registro de hallazgos ([09_hallazgos_mejoras.md](09_hallazgos_mejoras.md)).
