# Arquitectura — Parqueadero UFPS

El sistema migra de un backend único a microservicios, un servicio por vez. Este documento dice
a dónde vamos y en qué punto estamos.

## Objetivo: cuatro microservicios

Cada servicio tiene su propia base de datos y su propia API. Entre ellos solo se hablan por API;
ninguno lee las tablas de otro.

| Servicio | Responsabilidad | Datos propios |
|---|---|---|
| Identidad y verificación | Inicio de sesión, usuarios, vehículos, documentos y su aprobación | `usuarios`, `vehiculos`, `documentos` |
| Parqueadero | Zonas, espacios y cupos en tiempo real (WebSocket) | `zonas`, `espacios` |
| Accesos | Entradas, salidas y auditoría | `accesos`, `auditoria_accesos` |
| Visión (ALPR) | Lectura de placas a partir de una foto | Ninguno (sin estado) |

El navegador entra siempre por el **API Gateway** (nginx), que reparte cada ruta al servicio que
corresponde. Así el frontend conoce una sola dirección.

```
Navegador → gateway :8000 → /api/v1/alpr/*                      → visión
                          → /api/v1/zonas, espacios, reportes   → parqueadero
                          → /ws/*                               → parqueadero
                          → lo demás                            → identidad / accesos
```

## Estado actual

| Paso | Estado |
|---|---|
| 1. Gateway + visión con pantalla propia | Hecho |
| 2. Separar Parqueadero | Hecho |
| 3. Separar Identidad y verificación | Pendiente |
| 4. Accesos con su base y auditoría | Pendiente |

| Servicio | Carpeta | Base de datos |
|---|---|---|
| Parqueadero | `backend-parqueadero` | `parqueadero_zonas` (contenedor `db-parqueadero`, puerto 5434) |
| Identidad + Accesos (aún juntos) | `backend-core` | `parqueadero` (contenedor `db`, puerto 5433) |
| Visión | `backend-vision` | Ninguna |

Identidad y Accesos siguen juntos en `backend-core`. Parqueadero y Visión ya son independientes.

## Cómo se registra una entrada (dos bases de datos)

El cupo y el acceso viven en bases distintas, así que no hay una transacción que cubra los dos.
Se resuelve con compensación:

1. Accesos pide a Parqueadero ocupar el cupo (`POST /interno/cupos/ocupar`). Si no hay cupo,
   Parqueadero responde 409 y no se crea nada.
2. Accesos crea el acceso y su auditoría en su propia base.
3. Si el paso 2 falla, Accesos pide liberar el cupo (`POST /interno/cupos/liberar`).

La salida es simétrica: primero se libera el cupo y luego se confirma la salida; si la
confirmación falla, se vuelve a ocupar. Parqueadero avisa cada cambio por WebSocket.

La API `/interno` es solo entre servicios: el gateway no la publica.

## Decisiones

- **Gateway en nginx.** Es una pieza estándar, liviana y solo se configura; no hay código propio
  que mantener (`gateway/nginx.conf.template`).
- **Visión no conoce usuarios.** No tiene base de datos ni lógica de negocio. El gateway valida la
  sesión contra Identidad (`auth_request`) antes de dejar pasar la imagen.
- **Los servicios de atrás no publican puerto.** Solo el gateway es alcanzable desde fuera.
- **El rol viaja en el token.** Parqueadero autoriza con el JWT (misma `SECRET_KEY`) sin consultar
  la base de usuarios, así funciona aunque Identidad esté caído. Costo: un usuario desactivado
  conserva acceso a Parqueadero hasta que su token expire (8 horas).
- **Una base por servicio, en contenedores distintos.** Si una base se cae, el otro servicio sigue
  respondiendo lo que no dependa de ella.

## Lo que falta resolver

- **Separar Identidad de Accesos.** Hoy comparten base; `accesos` aún tiene llaves foráneas a
  `usuarios` y `vehiculos`, que pasarán a ser identificadores sin restricción.
- **Compensación fallida.** Si Parqueadero se cae justo entre ocupar y compensar, el contador
  queda desfasado y solo se deja un registro en el log; falta un mecanismo de reintento.

## Migrar una base existente

`backend-core` trae la migración `0003_separar_parqueadero`, que borra `zonas` y `espacios`.
Antes hay que copiar esos datos a la base nueva:

```
docker compose up -d db-parqueadero backend-parqueadero
docker compose exec backend-parqueadero alembic upgrade head
docker compose exec -T db pg_dump -U parqueadero -d parqueadero --data-only -t zonas -t espacios \
  | docker compose exec -T db-parqueadero psql -U parqueadero -d parqueadero_zonas -1
docker compose exec -e PARQUEADERO_DATOS_MIGRADOS=1 backend-core alembic upgrade head
```

En una instalación nueva basta `alembic upgrade head` en cada servicio.
