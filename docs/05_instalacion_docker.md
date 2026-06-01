# 05 — Instalación y Operación con Docker

Esta guía describe cómo instalar y operar el sistema **Restaurante Casa Vieja**
mediante Docker Compose, basándose en el archivo `docker-compose.yml` del
repositorio.

---

## 1. Requisitos previos

- **Docker Engine** y **Docker Compose v2** instalados y en ejecución.
- Acceso a internet (para descargar las imágenes `odoo:18` y `postgres:15`, y
  para el CDN de Kushki si se prueban pagos).
- Puerto **8071** libre en el host.
- Un respaldo de arranque dentro de `backups/`:
  - `backups/db_demo.dump` (dump de PostgreSQL en formato custom).
  - `backups/filestore/odoo/` (filestore correspondiente).

> El servicio `restore` **requiere** `backups/db_demo.dump` para iniciar. Sin
> él, el arranque falla con un mensaje de error explícito.

---

## 2. Estructura esperada del proyecto

```
Restaurante-Odoo-Das/
├── docker-compose.yml
├── addons/                 # Módulos personalizados (bind mount → /mnt/extra-addons)
│   ├── restaurant_casa_vieja_base/
│   ├── restaurant_delivery_orders/
│   ├── restaurant_table_reservations/
│   └── pay_kushki/
├── scripts/                # Scripts (bind mount → /scripts)
│   ├── backup.sh
│   ├── restore.sh
│   └── create_repartidores.py
└── backups/                # Respaldos (bind mount → /backups) — NO versionado
    ├── db_demo.dump
    └── filestore/odoo/
```

> **Importante:** la carpeta `backups/` **no** forma parte del control de
> versiones (no se asume incluida en el repositorio). Debe proveerse aparte. Si
> está excluida o vacía, el servicio `restore` no podrá restaurar.

### Servicios definidos en `docker-compose.yml`

| Servicio | Imagen | Puerto | Notas |
|----------|--------|--------|-------|
| `db` | `postgres:15` | interno | Usuario/clave `odoo/odoo`, base `postgres`. Healthcheck `pg_isready`. |
| `restore` | `postgres:15` | — | One-shot: restaura `db_demo.dump` + filestore en la base `odoo`. |
| `odoo` | `odoo:18` | `8071→8069` | Monta `./addons`, `./backups`, `./scripts`. Arranca con `-u restaurant_table_reservations -d odoo`. |
| `backup` | `postgres:15` | — | Perfil `tools`. Genera dump + copia del filestore. |

Volúmenes: `odoo-db-data` (datos de PostgreSQL) y `odoo-web-data` (filestore de
Odoo).

---

## 3. Comandos para levantar Docker

```bash
# Levantar todo el entorno en segundo plano
docker compose up -d
```

Secuencia de arranque (por dependencias):
1. `db` arranca y queda *healthy*.
2. `restore` se ejecuta una sola vez: elimina la base `odoo` previa, la recrea,
   restaura el dump, limpia los assets web cacheados y restaura el filestore.
3. `odoo` arranca cuando `restore` finaliza correctamente, actualizando el
   módulo `restaurant_table_reservations`.

Acceda luego a: **http://localhost:8071**

---

## 4. Comandos para revisar contenedores

```bash
# Estado de todos los servicios
docker compose ps

# Detalle de un contenedor
docker inspect proyectoDAS        # contenedor de Odoo
docker inspect proyectoDAS-db     # contenedor de la base
```

Nombres de contenedor definidos: `proyectoDAS` (odoo), `proyectoDAS-db` (db),
`proyectoDAS-restore` (restore), `proyectoDAS-backup` (backup).

---

## 5. Comandos para ver logs

```bash
# Logs de Odoo en vivo
docker compose logs -f odoo

# Logs de la base de datos
docker compose logs -f db

# Logs del proceso de restauración (one-shot)
docker compose logs restore

# Últimas 200 líneas de Odoo
docker compose logs --tail=200 odoo
```

---

## 6. Comandos para actualizar módulos

```bash
# Actualizar un módulo
docker compose exec odoo odoo -d odoo -u restaurant_delivery_orders --stop-after-init

# Actualizar varios módulos
docker compose exec odoo odoo -d odoo \
  -u restaurant_casa_vieja_base,restaurant_delivery_orders,restaurant_table_reservations \
  --stop-after-init

# Reiniciar Odoo tras la actualización
docker compose restart odoo
```

> El servicio `odoo` ya arranca actualizando `restaurant_table_reservations`. Para
> forzar la actualización de otros módulos, use los comandos anteriores.

---

## 7. Comandos para backup y restore

### Backup mediante el servicio (perfil `tools`)
```bash
docker compose --profile tools run --rm backup
```
Genera `backups/db_demo.dump` y copia el filestore a `backups/filestore/odoo/`,
filtrando huérfanos del filestore.

### Backup mediante el script (desde el host)
```bash
bash scripts/backup.sh
```

### Restore mediante el script
```bash
bash scripts/restore.sh
```
Recrea la base `odoo`, restaura el dump y el filestore, y reinicia Odoo.

### Restore automático
El servicio `restore` del `docker-compose.yml` ejecuta el restore en cada
`docker compose up`, antes de iniciar Odoo.

### Recrear el entorno desde cero (desde backup)
```bash
docker compose down -v     # elimina volúmenes (datos)
docker compose up -d       # restaura desde backups/db_demo.dump
```

---

## 8. Tareas operativas adicionales

### Crear usuarios repartidores
El script `scripts/create_repartidores.py` se ejecuta vía `odoo shell`:

```bash
docker compose exec odoo odoo shell -d odoo < scripts/create_repartidores.py
```

> Crea usuarios de ejemplo con contraseña `1234`. **Cámbielas** de inmediato
> (ver [SECURITY.md](../SECURITY.md)).

---

## 9. Problemas comunes y soluciones

| Problema | Causa probable | Solución |
|----------|----------------|----------|
| `restore` falla: "No existe /backups/db_demo.dump" | Falta el respaldo de arranque. | Coloque `db_demo.dump` (y el filestore) en `backups/`. |
| Odoo no arranca | El servicio `restore` no terminó con éxito. | Revise `docker compose logs restore`. |
| Puerto 8071 ocupado | Otro proceso usa el puerto. | Libere el puerto o cambie el mapeo en `docker-compose.yml`. |
| Cambios en `addons/` no se reflejan | Falta actualizar el módulo. | Ejecute el comando de actualización (sección 6). |
| Estilos/JS desactualizados | Assets web cacheados. | El restore limpia los assets; si persiste, actualice el módulo y reinicie Odoo. |
| Cambios no persisten tras `down -v` | `down -v` borra volúmenes. | Use `down` (sin `-v`) para conservar datos; o haga backup antes. |
| Permisos del filestore | Propiedad incorrecta tras restaurar. | El restore aplica `chmod`; el script aplica `chown odoo:odoo`. |

---

## 10. Notas

- Las credenciales `odoo/odoo` y la configuración `fsync=off` del `db` están
  pensadas para **desarrollo**. No usar tal cual en producción
  (ver [SECURITY.md](../SECURITY.md)).
- La base de datos por defecto es `odoo`.
- Para producción se recomienda un proxy inverso con HTTPS y credenciales
  propias; estos pasos están **fuera del alcance** de este entorno de taller.
