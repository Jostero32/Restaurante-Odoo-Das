# Restaurante Casa Vieja — Sistema Odoo 18

Sistema de gestión para el **Restaurante Casa Vieja**, construido sobre **Odoo 18**
y desplegado mediante **Docker Compose**. Reúne módulos personalizados para la
operación de pedidos a domicilio (delivery), reservas de mesa e integración de
pagos en línea, sobre una base común de roles y menús.

> Este repositorio incluye la documentación del taller académico de
> **Herramientas de Documentación, Pruebas y Evaluación de Software**.
> Toda la documentación se encuentra en la carpeta [docs/](docs/).

---

## Descripción general

Casa Vieja es un restaurante que requiere digitalizar dos canales de atención:

1. **Pedidos a domicilio (delivery)** integrados con la tienda en línea
   (e-commerce) de Odoo, con seguimiento del cliente desde el portal, asignación
   de repartidores, incidencias, calificaciones y facturación.
2. **Reservas de mesa** desde un formulario web público, con selección de zona,
   mesa, horario, arreglos especiales (decoración) y pre-orden de productos,
   con integración hacia el Punto de Venta (POS) de Odoo.

La integración de pagos **Kushki** se incorpora como complemento del flujo
web/e-commerce para permitir el pago digital con tarjeta.

## Objetivo

Proveer una plataforma unificada que permita al personal del restaurante
gestionar pedidos a domicilio y reservas de mesa, y a los clientes realizar y
dar seguimiento a ambos procesos desde la web, reutilizando los módulos estándar
de Odoo (ventas, facturación, portal, POS y pagos).

## Alcance

El alcance documentado se limita a lo que existe actualmente en el código:

- Módulo base del restaurante (`restaurant_casa_vieja_base`).
- Módulo de pedidos a domicilio (`restaurant_delivery_orders`).
- Módulo de reservas de mesa (`restaurant_table_reservations`).
- Integración de pago **Kushki** (`pay_kushki`) como integración complementaria
  asociada al flujo de delivery/e-commerce.

> Un módulo de **cocina** (tablero de cocina, pantalla de mesero, etc.) **no está
> desarrollado** y se menciona únicamente como mejora futura. El grupo de
> seguridad "Cocinero" existe en la base, pero no hay un módulo de cocina asociado.

## Tecnologías usadas

| Componente            | Tecnología                                   |
|-----------------------|----------------------------------------------|
| ERP / Framework       | Odoo 18 (imagen oficial `odoo:18`)           |
| Base de datos         | PostgreSQL 15 (imagen `postgres:15`)         |
| Orquestación          | Docker Compose                               |
| Lenguaje servidor     | Python 3.12 (runtime de la imagen Odoo 18)   |
| Frontend / Portal     | QWeb, XML, JavaScript, SCSS/CSS              |
| Pagos en línea        | Kushki (Kajita / checkout JS, CDN externo)   |
| Localización          | `l10n_ec_website_sale` (Ecuador)             |

## Módulos personalizados

| Módulo                          | Rol            | Resumen |
|---------------------------------|----------------|---------|
| `restaurant_casa_vieja_base`    | Base común     | Categoría, grupos de seguridad y menú raíz del restaurante. |
| `restaurant_delivery_orders`    | Principal      | Pedidos a domicilio, repartidores, incidencias, calificaciones, horarios, facturación y portal. |
| `restaurant_table_reservations` | Principal      | Reservas de mesa, zonas, mesas, pre-orden, arreglos especiales e integración POS. |
| `pay_kushki`                    | Integración    | Proveedor de pago Kushki para el flujo de e-commerce/delivery. |

Detalle técnico en [docs/03_documentacion_tecnica.md](docs/03_documentacion_tecnica.md).

## Flujo general del sistema

```
                ┌──────────────────────────────────────────────┐
                │            Restaurante Casa Vieja             │
                └──────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────┴────────────────────────────┐
        │                                                          │
   DELIVERY                                                    RESERVAS
   (e-commerce + portal)                                       (web + POS)
        │                                                          │
  Cliente compra en /shop ──► sale.order ──► restaurant.delivery.order
        │   (pago Kushki opcional)                │                │
        │                                         ▼                ▼
   Portal /my/delivery  ◄── notificaciones    Repartidor      Cliente reserva
   (seguimiento, incidencias,                  actualiza       en /reservas
    calificación, facturas)                    estado          │
                                                                ▼
                                                  restaurant.table.reservation
                                                                │
                                                       Mesero confirma / sienta
                                                                ▼
                                                       POS (pos.order draft,
                                                        pre-orden + arreglo)
```

## Requisitos previos

- **Docker** y **Docker Compose** (v2) instalados.
- Puertos disponibles: `8071` (Odoo) en el host.
- Un respaldo `backups/db_demo.dump` y su `backups/filestore/odoo/` para el
  arranque inicial (el servicio `restore` los requiere). Ver
  [docs/05_instalacion_docker.md](docs/05_instalacion_docker.md).

> La carpeta `backups/` no se versiona en el repositorio. Se debe proveer el
> respaldo por fuera del control de versiones (ver `.gitignore` y CONTRIBUTING).

## Instalación con Docker Compose

```bash
# 1. Levantar el entorno completo (db + restore + odoo)
docker compose up -d

# 2. Verificar que los contenedores estén arriba
docker compose ps

# 3. Acceder a Odoo
#    http://localhost:8071
```

El servicio `restore` restaura automáticamente `backups/db_demo.dump` y el
filestore antes de iniciar Odoo. El servicio `odoo` arranca actualizando el
módulo `restaurant_table_reservations` sobre la base `odoo`.

## Comandos principales

```bash
# Iniciar entorno
docker compose up -d

# Detener entorno (conservando volúmenes)
docker compose down

# Detener y borrar volúmenes (fuerza recreación desde backup)
docker compose down -v

# Ver estado de contenedores
docker compose ps

# Ver logs de Odoo
docker compose logs -f odoo

# Crear backup (perfil de herramientas)
docker compose --profile tools run --rm backup
```

## Estructura del repositorio

```
Restaurante-Odoo-Das/
├── docker-compose.yml          # Orquestación: db, restore, odoo, backup
├── README.md                   # Este archivo
├── CONTRIBUTING.md             # Guía de colaboración
├── CODE_OF_CONDUCT.md          # Código de conducta del equipo
├── CHANGELOG.md                # Historial de cambios
├── SECURITY.md                 # Recomendaciones de seguridad
├── .gitignore
├── addons/                     # Módulos personalizados de Odoo
│   ├── restaurant_casa_vieja_base/
│   ├── restaurant_delivery_orders/
│   ├── restaurant_table_reservations/
│   └── pay_kushki/
├── scripts/                    # Scripts operativos (backup, restore, altas)
│   ├── backup.sh
│   ├── restore.sh
│   ├── create_repartidores.py
│   └── update_reservas_view.py
├── backups/                    # Respaldos (NO versionado)
└── docs/                       # Documentación del taller
    ├── 01_descripcion_general.md
    ├── 02_manual_usuario.md
    ├── 03_documentacion_tecnica.md
    ├── 04_integraciones.md
    ├── 05_instalacion_docker.md
    ├── 06_plan_pruebas.md
    ├── 07_casos_prueba_funcionales.md
    ├── 08_prueba_rendimiento_jmeter.md
    ├── 09_hallazgos_mejoras.md
    └── evidencias/
        └── README.md
```

## Cómo actualizar módulos

```bash
# Actualizar un módulo específico
docker compose exec odoo odoo -d odoo -u restaurant_delivery_orders --stop-after-init

# Actualizar todos los módulos personalizados
docker compose exec odoo odoo -d odoo \
  -u restaurant_casa_vieja_base,restaurant_delivery_orders,restaurant_table_reservations \
  --stop-after-init
```

Tras la actualización, reinicie el servicio Odoo si fuese necesario:

```bash
docker compose restart odoo
```

## Cómo hacer backup y restore

El repositorio incluye scripts en `scripts/` y servicios en `docker-compose.yml`.

```bash
# Backup mediante el servicio (perfil tools)
docker compose --profile tools run --rm backup

# Backup mediante el script (desde el host)
bash scripts/backup.sh

# Restore mediante el script
bash scripts/restore.sh
```

El servicio `restore` del `docker-compose.yml` se ejecuta automáticamente al
hacer `docker compose up` y restaura la base y el filestore desde
`backups/db_demo.dump`. Detalles en
[docs/05_instalacion_docker.md](docs/05_instalacion_docker.md).

## Enlaces a la documentación (docs/)

| Documento | Contenido |
|-----------|-----------|
| [01_descripcion_general.md](docs/01_descripcion_general.md) | Descripción narrativa, arquitectura, roles y alcance. |
| [02_manual_usuario.md](docs/02_manual_usuario.md) | Manual para usuarios no técnicos. |
| [03_documentacion_tecnica.md](docs/03_documentacion_tecnica.md) | Documentación para desarrolladores. |
| [04_integraciones.md](docs/04_integraciones.md) | Integraciones (sale.order, portal, POS, Kushki). |
| [05_instalacion_docker.md](docs/05_instalacion_docker.md) | Instalación y operación con Docker. |
| [06_plan_pruebas.md](docs/06_plan_pruebas.md) | Plan de pruebas. |
| [07_casos_prueba_funcionales.md](docs/07_casos_prueba_funcionales.md) | Casos de prueba funcionales. |
| [08_prueba_rendimiento_jmeter.md](docs/08_prueba_rendimiento_jmeter.md) | Prueba de rendimiento con JMeter. |
| [09_hallazgos_mejoras.md](docs/09_hallazgos_mejoras.md) | Hallazgos y mejoras futuras. |
| [evidencias/README.md](docs/evidencias/README.md) | Guía de capturas y evidencias. |

## Recomendaciones básicas de mantenimiento

- Realizar **backups periódicos** antes de actualizar módulos o la imagen de Odoo.
- Mantener los **respaldos fuera del repositorio** (no versionar `backups/`).
- Revisar los **logs** (`docker compose logs -f odoo`) ante cualquier
  comportamiento inesperado, especialmente tras una actualización.
- No exponer el puerto de la base de datos a redes públicas.
- Cambiar las **credenciales por defecto** (`odoo/odoo`) en cualquier entorno
  distinto al de desarrollo local. Ver [SECURITY.md](SECURITY.md).

## Flujo de trabajo (ramas)

- `main`: rama principal, punto formal de arranque.
- `develop`: rama de integración con el estado funcional del proyecto.
- `feature/*`: cada avance funcional vive en una rama `feature/*` y se integra a
  `develop` mediante merge commit. Detalle en [CONTRIBUTING.md](CONTRIBUTING.md).

## Colaboradores del historial

- Kevin Carrasco: infraestructura, backups, integración y documentación.
- Marco Serrano: módulo base del restaurante.
- Alejandro Andrade: módulo de pedidos delivery.
- Jonathan Lozada: módulo de reservas de mesas.

## Licencia

Los módulos personalizados se distribuyen bajo licencia **LGPL-3**. El módulo
`pay_kushki` es de un autor externo (Dainier Escalona) bajo LGPL-3.
