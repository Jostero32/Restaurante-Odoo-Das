# Política y Recomendaciones de Seguridad

Este documento reúne recomendaciones de seguridad para el proyecto
**Restaurante Casa Vieja (Odoo 18)**, tanto para entornos de desarrollo como
para una eventual puesta en producción.

> **Nota:** El entorno provisto por `docker-compose.yml` usa credenciales por
> defecto pensadas para **desarrollo local**. No debe usarse tal cual en
> producción.

## 1. Credenciales

- **Cambiar las credenciales por defecto.** El `docker-compose.yml` define el
  usuario y contraseña de PostgreSQL como `odoo`/`odoo`. En cualquier entorno
  distinto al local, estas credenciales deben modificarse.
- Definir una **contraseña maestra de Odoo** (admin master password) robusta
  para proteger la gestión de bases de datos.
- Usar **contraseñas fuertes y únicas** para los usuarios administradores de
  Odoo.
- El script `scripts/create_repartidores.py` crea usuarios repartidores con una
  contraseña de ejemplo (`1234`). Estas contraseñas deben **cambiarse
  inmediatamente** y nunca usarse en producción.

## 2. Variables y datos sensibles

- Mantener las variables sensibles (credenciales, llaves de API) **fuera del
  repositorio**, preferentemente en archivos `.env` (ya excluidos por
  `.gitignore`) o en un gestor de secretos.
- **Credenciales de Kushki:** los campos `kushki_publicmerchantmd`,
  `kushki_privatemerchantmd` y `kushki_kformid` del proveedor de pago son
  sensibles. El *Private Merchant ID* **no debe** exponerse ni versionarse.
  Configurarlos en el entorno de prueba/producción a través de la interfaz de
  Odoo y no en archivos del repositorio.
- Verificar que el campo "Test Environment" de Kushki esté correctamente
  configurado según el entorno (pruebas vs. producción).
- No registrar (log) datos de tarjetas ni tokens de pago.

## 3. Backups

- Realizar **backups periódicos** de la base de datos y el filestore (ver
  `scripts/backup.sh` y el servicio `backup` del `docker-compose.yml`).
- **No versionar** los backups: la carpeta `backups/` no debe subirse al
  repositorio. Contiene datos potencialmente personales de clientes.
- Almacenar los respaldos en una ubicación **segura y con acceso restringido**,
  preferentemente cifrada.
- Probar periódicamente la **restauración** (`scripts/restore.sh`) para
  garantizar que los respaldos son válidos.
- Aplicar una política de **retención** y borrado seguro de respaldos antiguos.

## 4. Accesos de Odoo

- Restringir el acceso al backend de Odoo solo al personal autorizado.
- No exponer el puerto de **PostgreSQL** a redes públicas; mantenerlo accesible
  solo dentro de la red de contenedores.
- En producción, servir Odoo detrás de un **proxy inverso con HTTPS/TLS**.
- Mantener actualizada la imagen de Odoo y de PostgreSQL para incorporar
  parches de seguridad.
- Deshabilitar o proteger el listado/creación de bases de datos
  (`list_db = False`) en producción.

## 5. Control de permisos por grupos

El sistema define roles mediante grupos de seguridad en
`restaurant_casa_vieja_base`. La asignación de usuarios a grupos debe seguir el
**principio de mínimo privilegio**:

| Grupo | Alcance previsto |
|-------|------------------|
| Repartidor Restaurante | Solo lectura/actualización de estado de sus pedidos asignados. |
| Cocinero Restaurante | Solo lectura sobre modelos operativos. |
| Mesero Restaurante | Toma de reservas y pedidos; sin eliminación. |
| Administración Restaurante | Crea y edita registros; sin eliminación. |
| Administrador Restaurante | Control total (CRUD). |

Recomendaciones:

- Asignar a cada usuario **únicamente** el grupo que corresponde a su función.
- Revisar periódicamente la pertenencia a grupos, especialmente la del grupo
  **Administrador**.
- Las reglas de registro (`ir.rule`) restringen el acceso del portal a los datos
  propios del cliente y el del repartidor a sus pedidos. No relajar estas reglas
  sin una revisión de seguridad.
- Validar los permisos definidos en
  `security/ir.model.access.csv` de cada módulo antes de cualquier despliegue.

## 6. Recomendaciones para producción

- Usar credenciales y secretos exclusivos de producción, distintos a los de
  desarrollo.
- Activar **HTTPS** y forzar redirección desde HTTP.
- Configurar **copias de seguridad automáticas** y monitoreo.
- Limitar el acceso administrativo por IP cuando sea posible.
- Mantener un registro (log) de accesos y revisar eventos anómalos.
- Aplicar actualizaciones de seguridad de Odoo, PostgreSQL y del sistema base.
- Revisar la configuración del proveedor de pago Kushki para usar el entorno de
  producción y credenciales válidas, manteniéndolas fuera del repositorio.

## Reporte de vulnerabilidades

Si detecta una vulnerabilidad o una exposición de credenciales, repórtela de
inmediato al equipo responsable del proyecto y, de tratarse de credenciales
comprometidas, proceda a **rotarlas** sin demora.

> Los datos de contacto del equipo responsable están **pendientes de validar**
> según la organización del taller. `[COMPLETAR]`
