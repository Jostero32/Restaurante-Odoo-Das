# Restaurante Odoo - Casa Vieja

Repositorio del proyecto Restaurante Odoo para la gestion de configuracion, modulos personalizados, respaldos y scripts operativos.

## Flujo de trabajo

- `main`: rama principal vacia, usada como punto formal de arranque.
- `develop`: rama de integracion con el estado funcional del proyecto.
- `feature/base-restaurante`: trabajo funcional del modulo base.
- `feature/delivery`: trabajo funcional del modulo delivery.
- `feature/reservas`: trabajo funcional del modulo reservas.
- `feature/integracion-documentacion`: scripts, documentacion y cierre de integracion.

No se usan ramas `modulo/*`; cada avance funcional vive en una rama `feature/*`
y se integra a `develop` mediante merge commit.

## Colaboradores del historial

- Kevin Carrasco: infraestructura, backups, integracion y documentacion.
- Marco Serrano: modulo base del restaurante.
- Alejandro Andrade: modulo de pedidos delivery.
- Jonathan Lozada: modulo de reservas de mesas.

## Modulos incluidos

- `restaurant_casa_vieja_base`: grupos de seguridad y menu raiz del restaurante.
- `restaurant_delivery_orders`: pedidos a domicilio, repartidor, estados y gestion operativa.
- `restaurant_table_reservations`: mesas, reservas, validaciones de horario y flujo de atencion.

## Servicios

- `db`: PostgreSQL 15.
- `restore`: restaura `backups/db_demo.dump` y filestore antes de iniciar Odoo.
- `odoo`: instancia Odoo 18 con addons personalizados.
- `backup`: servicio auxiliar para generar respaldo.

## Comandos utiles

Iniciar entorno:

```bash
docker compose up -d
```

Crear backup:

```bash
docker compose --profile tools run --rm backup
```

Recrear desde backup:

```bash
docker compose down -v
docker compose up -d
```

Actualizar modulos:

```bash
docker compose exec odoo odoo -d odoo \
  -u restaurant_casa_vieja_base,restaurant_delivery_orders,restaurant_table_reservations \
  --stop-after-init
```

## Scripts

- `scripts/backup.sh`: respaldo manual de base y filestore.
- `scripts/restore.sh`: restauracion manual de base y filestore.
- `scripts/create_repartidores.py`: alta de usuarios repartidores desde `odoo shell`.
