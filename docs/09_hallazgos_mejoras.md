# 09 — Hallazgos y Mejoras

Este documento registra los **hallazgos** detectados durante las pruebas y las
**mejoras futuras** propuestas para el sistema Restaurante Casa Vieja.

---

## 1. Tabla de hallazgos

Cada hallazgo incluye: ID, descripción, módulo, severidad, evidencia, posible
causa, recomendación y estado.

Severidad: `Alta` / `Media` / `Baja`.
Estado: `Abierto` / `En análisis` / `Resuelto` / `Descartado`.

> Las filas marcadas como **[EJEMPLO]** son ilustrativas de cómo registrar un
> hallazgo. **No** corresponden a defectos confirmados del sistema. Reemplácelas
> o complételas con hallazgos reales durante la ejecución de las pruebas.

| ID | Descripción | Módulo | Severidad | Evidencia | Posible causa | Recomendación | Estado |
|----|-------------|--------|-----------|-----------|---------------|---------------|--------|
| H-01 **[EJEMPLO]** | Al reservar fuera del horario operativo el mensaje de error no es suficientemente claro para el usuario. | Reservas | Baja | `[COMPLETAR]` | Texto de validación genérico. | Mejorar el copy del mensaje y mostrarlo cerca del campo de hora. | `[EJEMPLO]` |
| H-02 **[EJEMPLO]** | El endpoint `/reservas/availability` muestra latencia elevada con 10 usuarios concurrentes. | Reservas | Media | `[COMPLETAR]` | Consultas SQL de solapamiento sin índice óptimo. | Revisar índices y cachear resultados de disponibilidad. | `[EJEMPLO]` |
| H-03 **[EJEMPLO]** | El formulario de reservas no es totalmente responsive en pantallas pequeñas. | Reservas | Baja | `[COMPLETAR]` | Estilos CSS no adaptados a móvil. | Ajustar `reservation.css` para breakpoints móviles. | `[EJEMPLO]` |
| H-04 **[EJEMPLO]** | Las credenciales de Kushki por defecto apuntan al entorno UAT. | Pagos (Kushki) | Media | `[COMPLETAR]` | Configuración de demostración. | Documentar y configurar credenciales productivas fuera del repositorio. | `[EJEMPLO]` |
| H-05 **[EJEMPLO]** | El grupo "Cocinero" existe sin funcionalidad asociada. | Base | Baja | `[COMPLETAR]` | Rol previsto para un módulo de cocina aún no desarrollado. | Mantener como base para el futuro módulo de cocina. | `[EJEMPLO]` |
| `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` |
| `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` |

---

## 2. Observaciones derivadas del análisis del código

Las siguientes observaciones surgen de la revisión de la documentación y el
código; **no** son defectos confirmados, sino puntos a tener en cuenta durante
las pruebas:

- **Acoplamiento de horario:** las reservas reutilizan el horario de delivery
  (`restaurant.delivery.schedule`). Un cambio en el horario de delivery afecta
  también a las reservas. *Pendiente de validar* si es el comportamiento deseado.
- **Dependencia de sesión POS:** las pruebas de integración de reservas con el
  POS requieren una sesión POS abierta; de lo contrario, no se crea la orden POS.
- **Dependencia de CDN externo:** el flujo de Kushki carga
  `kushki-checkout.js` desde un CDN externo; su disponibilidad condiciona las
  pruebas de pago.
- **Credenciales y datos sensibles:** revisar que no se versionen credenciales de
  Kushki ni respaldos (ver [SECURITY.md](../SECURITY.md)).

---

## 3. Mejoras futuras

### 3.1 Módulo de cocina (no desarrollado)
- Crear un **módulo de cocina** que gestione la preparación de pedidos delivery y
  de pedidos de salón.
- **Tablero Kanban de cocina** para visualizar y mover los pedidos por etapas de
  preparación.
- **Pantalla de mesero** dedicada para la gestión del salón y la comunicación con
  cocina.

> El grupo de seguridad "Cocinero" ya existe en la base y serviría como punto de
> partida para los permisos de este módulo.

### 3.2 Experiencia de usuario
- **Mejora responsive** de los formularios web de reservas y del portal de
  delivery, optimizando la visualización en dispositivos móviles.
- Mensajes de validación más claros y contextualizados.

### 3.3 Calidad y automatización
- **Automatización de pruebas** funcionales y de regresión (por ejemplo, con el
  framework de pruebas de Odoo y/o pruebas end-to-end del portal).
- **Pipeline CI/CD** que ejecute las pruebas y valide la actualización de módulos
  en cada cambio, antes de integrar a `develop`/`main`.

### 3.4 Operación
- Horario operativo **independiente** para reservas, desacoplado del de delivery.
- Endurecimiento de la integración Kushki para producción (credenciales,
  manejo de errores y registro).
- Monitoreo y alertas del entorno (logs, salud de contenedores, respaldos).

---

## 4. Seguimiento

| Mejora | Prioridad | Responsable | Estado |
|--------|-----------|-------------|--------|
| Módulo de cocina (Kanban + pantalla mesero) | `[COMPLETAR]` | `[COMPLETAR]` | Propuesta |
| Mejora responsive | `[COMPLETAR]` | `[COMPLETAR]` | Propuesta |
| Automatización de pruebas | `[COMPLETAR]` | `[COMPLETAR]` | Propuesta |
| Pipeline CI/CD | `[COMPLETAR]` | `[COMPLETAR]` | Propuesta |
| Horario independiente de reservas | `[COMPLETAR]` | `[COMPLETAR]` | Propuesta |
| Endurecimiento de Kushki para producción | `[COMPLETAR]` | `[COMPLETAR]` | Propuesta |
