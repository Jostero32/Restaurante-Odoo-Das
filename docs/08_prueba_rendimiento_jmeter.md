# 08 — Prueba de Rendimiento con JMeter

## 1. Objetivo de la prueba

Evaluar el comportamiento del sistema bajo **concurrencia** en las rutas web del
módulo de reservas, midiendo tiempos de respuesta, throughput y porcentaje de
errores, con el fin de identificar posibles cuellos de botella antes de un uso
real con varios usuarios simultáneos.

## 2. Justificación del uso de JMeter

**Apache JMeter** es una herramienta de código abierto, ampliamente usada para
pruebas de carga y rendimiento de aplicaciones web. Se elige porque:

- Permite simular **múltiples usuarios concurrentes** sin instrumentar el código.
- Genera **métricas estándar** (tiempos, throughput, % de error, KB/s) y reportes
  visuales (gráficos, *summary report*, *aggregate report*).
- Es **reproducible**: el plan de pruebas (`.jmx`) puede versionarse y reejecutarse.
- No requiere modificar el sistema bajo prueba (Odoo), respetando el alcance del
  taller (solo documentación y pruebas, sin cambios de código).

## 3. Consideraciones previas

- Las rutas de reservas requieren **autenticación** (`auth="user"`). Para
  ejecutar JMeter con sesión, se debe gestionar el **login** y la **cookie de
  sesión** (HTTP Cookie Manager) y el token CSRF cuando aplique. Esto está
  **pendiente de validar** según la configuración del entorno.
- Las pruebas se ejecutan contra el **entorno local** (`http://localhost:8071`)
  con datos de demostración restaurados.
- No se realizan pruebas de carga contra la pasarela real de Kushki.

## 4. Escenarios de prueba

### Escenario 1 — GET `/reservas`
- **Ruta:** `GET http://localhost:8071/reservas`
- **Descripción:** carga del formulario de reservas. Mide el tiempo de respuesta
  de la página principal de reservas bajo concurrencia.
- **Autenticación:** requerida (usuario de portal). Gestionar sesión con Cookie
  Manager.

### Escenario 2 — Consulta de disponibilidad `GET /reservas/availability`
- **Ruta:** `GET http://localhost:8071/reservas/availability`
- **Parámetros (query string):** `zone`, `party_size`, `date`, `time`.
  Ejemplo: `?zone=main&party_size=2&date=2026-06-15&time=20:00`
- **Descripción:** endpoint JSON que devuelve mesas disponibles y horas válidas.
  Mide el tiempo de la consulta de disponibilidad (incluye acceso a base de datos
  y cálculo de slots/solapamientos).
- **Autenticación:** requerida (usuario de portal).

> Ambas rutas existen en el controlador
> `restaurant_table_reservations/controllers/main.py`.

## 5. Configuración sugerida (Thread Group)

| Parámetro | Valor |
|-----------|-------|
| Usuarios concurrentes (threads) | **10** |
| Ramp-up (período de arranque) | **10 segundos** |
| Iteraciones por usuario (loop count) | **5** |
| Total de peticiones por escenario | 10 × 5 = **50** |

Elementos recomendados del plan de pruebas JMeter:
- **HTTP Cookie Manager** (para mantener la sesión autenticada).
- **HTTP Header Manager** (cabeceras, p. ej. `Content-Type` si aplica).
- **HTTP Request Defaults** (servidor `localhost`, puerto `8071`).
- **(Opcional) HTTP Request de login** previo para obtener la sesión y, si es
  necesario, un **CSS/Regex Extractor** del token CSRF.
- **Listeners:** *Summary Report*, *Aggregate Report* y *View Results Tree* (este
  último solo para depуración, no para la medición final).

## 6. Métricas a registrar

| Métrica | Descripción |
|---------|-------------|
| **Tiempo promedio (Average)** | Tiempo medio de respuesta (ms). |
| **Mínimo (Min)** | Tiempo de respuesta más bajo (ms). |
| **Máximo (Max)** | Tiempo de respuesta más alto (ms). |
| **Throughput** | Peticiones procesadas por segundo (o por minuto). |
| **% de error (Error %)** | Porcentaje de peticiones fallidas. |
| **KB/sec** | Rendimiento de transferencia (kilobytes por segundo). |

## 7. Tabla de resultados

### Escenario 1 — GET `/reservas`

| Métrica | Valor |
|---------|-------|
| Muestras (samples) | `[COMPLETAR]` |
| Tiempo promedio (ms) | `[COMPLETAR]` |
| Mínimo (ms) | `[COMPLETAR]` |
| Máximo (ms) | `[COMPLETAR]` |
| Throughput | `[COMPLETAR]` |
| Error % | `[COMPLETAR]` |
| KB/sec | `[COMPLETAR]` |

### Escenario 2 — GET `/reservas/availability`

| Métrica | Valor |
|---------|-------|
| Muestras (samples) | `[COMPLETAR]` |
| Tiempo promedio (ms) | `[COMPLETAR]` |
| Mínimo (ms) | `[COMPLETAR]` |
| Máximo (ms) | `[COMPLETAR]` |
| Throughput | `[COMPLETAR]` |
| Error % | `[COMPLETAR]` |
| KB/sec | `[COMPLETAR]` |

## 8. Análisis de resultados

> Completar tras la ejecución.

- **Tiempos de respuesta:** `[COMPLETAR]` — comparar el promedio frente a un
  umbral aceptable (p. ej. < 1000 ms para la página y < 500 ms para el endpoint
  JSON, *valores de referencia a validar*).
- **Throughput:** `[COMPLETAR]` — peticiones por segundo sostenidas.
- **Errores:** `[COMPLETAR]` — analizar las causas de cualquier error (timeouts,
  401/403 por sesión, 500).
- **Comparación entre escenarios:** `[COMPLETAR]` — el endpoint de disponibilidad
  realiza consultas a base de datos; evaluar si es más lento que la carga de la
  página.
- **Cuellos de botella detectados:** `[COMPLETAR]`.
- **Conclusiones y recomendaciones:** `[COMPLETAR]`.

## 9. Evidencias (capturas)

[CAPTURA PENDIENTE: configuración del Thread Group en JMeter (10 usuarios, ramp-up 10s, 5 iteraciones)]
[CAPTURA PENDIENTE: Summary Report del Escenario 1 (/reservas)]
[CAPTURA PENDIENTE: Summary Report del Escenario 2 (/reservas/availability)]
[CAPTURA PENDIENTE: Aggregate Report comparativo]
[CAPTURA PENDIENTE: gráfico de resultados / Response Time Graph]

> Guardar las capturas en [evidencias/](evidencias/) siguiendo la nomenclatura
> indicada (prefijos `09_jmeter_*`).
