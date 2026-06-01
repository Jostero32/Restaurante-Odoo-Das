# Guía de Colaboración — Restaurante Casa Vieja

Este documento define las reglas de colaboración del equipo para el proyecto
**Restaurante Casa Vieja (Odoo 18)**. El objetivo es mantener un historial
ordenado, código revisable y un repositorio limpio y seguro.

## Reglas generales de colaboración

- Toda contribución se realiza mediante **ramas** y **pull requests** (PR),
  nunca empujando directamente a `main` ni a `develop`.
- Antes de empezar, sincronice su rama con `develop`.
- Cada cambio funcional debe estar acompañado de su documentación
  correspondiente (ver "Reglas para documentar cambios").
- No mezcle cambios no relacionados en un mismo PR.

## Flujo de ramas

| Rama         | Propósito |
|--------------|-----------|
| `main`       | Rama principal estable. Punto formal de arranque/release. |
| `develop`    | Rama de integración con el estado funcional del proyecto. |
| `feature/*`  | Trabajo funcional de cada característica o módulo. |

Reglas:

1. Cada avance funcional vive en una rama `feature/<descripcion-corta>`
   (por ejemplo: `feature/delivery-facturacion`, `feature/reservas`).
2. Las ramas `feature/*` se integran a `develop` mediante **merge commit**.
3. `develop` se promueve a `main` cuando el estado es estable y verificado.
4. No se usan ramas con prefijo `modulo/*`.

```
main  ───────────────●────────────────────────●──────►
                     ▲                        ▲
develop ──●────●────●────●────●────●────●────●──────►
          ▲         ▲              ▲
     feature/base  feature/delivery  feature/reservas
```

## Convención de commits

Se recomienda redactar mensajes claros y descriptivos, en español, con un
encabezado conciso y, opcionalmente, un cuerpo que explique el "porqué".

Formato sugerido (inspirado en *Conventional Commits*):

```
<tipo>: <resumen en imperativo>

[cuerpo opcional explicando el motivo del cambio]
```

Tipos sugeridos:

| Tipo       | Uso |
|------------|-----|
| `feat`     | Nueva funcionalidad. |
| `fix`      | Corrección de errores. |
| `docs`     | Cambios de documentación. |
| `refactor` | Reorganización sin cambio funcional. |
| `test`     | Adición o ajuste de pruebas. |
| `chore`    | Tareas de mantenimiento, infraestructura o scripts. |

Ejemplos:

```
feat: agregar pre-orden de productos a la reserva de mesa
fix: evitar doble cargo del arreglo especial en POS
docs: documentar rutas web del portal de delivery
```

## Proceso para pull requests

1. Cree su rama `feature/*` a partir de `develop`.
2. Realice commits pequeños y coherentes.
3. Verifique que los módulos se actualicen sin error
   (`docker compose exec odoo odoo -d odoo -u <modulo> --stop-after-init`).
4. Abra un PR hacia `develop` describiendo:
   - Qué cambia y por qué.
   - Módulos afectados.
   - Pasos de prueba realizados (referencie casos de
     [docs/07_casos_prueba_funcionales.md](docs/07_casos_prueba_funcionales.md)).
   - Capturas o evidencias si aplica.
5. Solicite revisión de al menos un integrante del equipo.

## Revisión de código

- Todo PR debe ser revisado por al menos **una persona distinta** al autor.
- El revisor valida: corrección funcional, seguridad (permisos y reglas de
  acceso), legibilidad y consistencia con el código existente.
- No se documenta cocina como funcionalidad desarrollada: si un PR la incluye,
  debe tratarse explícitamente como mejora futura o módulo aparte.
- Los comentarios de revisión se resuelven antes del merge.

## Reglas para documentar cambios

- Todo cambio funcional actualiza, cuando corresponda:
  - El **CHANGELOG.md** (sección *Unreleased* / próxima versión).
  - La documentación técnica en [docs/03_documentacion_tecnica.md](docs/03_documentacion_tecnica.md).
  - El manual de usuario en [docs/02_manual_usuario.md](docs/02_manual_usuario.md) si afecta a usuarios finales.
- Si se agregan o modifican **rutas web**, modelos o estados, debe reflejarse en
  la documentación de integraciones ([docs/04_integraciones.md](docs/04_integraciones.md)).
- La documentación se escribe en **español**, con tono claro y técnico.

## Reglas para no subir archivos sensibles ni pesados

El archivo `.gitignore` ya excluye `.env`, archivos compilados de Python
(`*.pyc`, `__pycache__/`) y artefactos del sistema operativo. Además:

- **No** subir respaldos pesados (`backups/`, `*.dump`, `*.sql`).
- **No** subir el **filestore** de Odoo ni adjuntos de la base de datos.
- **No** subir credenciales, llaves de API, ni archivos `.env`.
- **No** subir las credenciales reales de **Kushki** (merchant IDs públicos y
  privados). Use entornos de prueba y configúrelos por fuera del repositorio.
- **No** subir volcados de base de datos con datos personales de clientes.

> Si por error se versionó un archivo sensible o pesado, notifíquelo al equipo
> para depurar el historial y rotar las credenciales afectadas.

## Estilo de código

- Seguir las convenciones de Odoo 18 (estructura de módulos, nombres de modelos
  `restaurant.*`, métodos `_compute_*`, `action_*`, etc.).
- Mantener la densidad de comentarios y el estilo del código circundante.
- No introducir cambios de formato masivos no relacionados con el PR.
