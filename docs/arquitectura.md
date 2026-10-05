# Arquitectura — Parqueadero UFPS

El sistema migra de un backend único a microservicios, un servicio por vez. Este documento dice
a dónde vamos y en qué punto estamos.

## Objetivo: cuatro microservicios

Cada servicio tiene su propia base de datos y su propia API. Entre ellos solo se hablan por API;
ninguno lee las tablas de otro.

| Servicio | Responsabilidad | Datos propios |
|---|---|---|
| Identidad y verificación | Inicio de sesión, usuarios, vehículos, documentos y su aprobación | `usuarios`, `vehiculos`, `documentos`, `auditoria_identidad` |
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

## Servicio de Identidad: contrato

Lo que tendrá `backend-identidad` cuando se separe de `backend-core` (paso 3). Todavía no está
construido; los pasos están en [`pendientes.md`](pendientes.md).

### Nombres y puertos

| Qué | Valor |
|---|---|
| Servicio | `backend-identidad`, puerto interno 8003 (sin puerto publicado) |
| Base de datos | `parqueadero_identidad`, contenedor `db-identidad`, puerto 5435 en el host |
| Tablas | `usuarios`, `vehiculos`, `documentos`, `auditoria_identidad` |
| Archivos subidos | Volumen propio, privado y con descarga autenticada |

Rutas que el gateway le envía: `/api/v1/auth`, `/usuarios`, `/vehiculos`, `/documentos` y
`/verificaciones`. `/api/v1/accesos` y `/api/v1/auditoria` siguen en Accesos.

### Token

Solo Identidad emite tokens (`POST /api/v1/auth/login`). Son JWT firmados con HS256 y la
`SECRET_KEY` compartida, válidos 8 horas.

| Claim | Contenido |
|---|---|
| `sub` | Identificador del usuario |
| `rol` | `estudiante`, `docente`, `administrativo`, `vigilante` o `admin` |
| `exp` | Vencimiento |

Accesos y Parqueadero autorizan solo con la firma y el `rol` del token, sin consultar a
Identidad. Costo: un usuario desactivado conserva acceso a ambos hasta que su token expire.

### API interna

La usa Accesos al registrar una entrada. Las respuestas no llevan nombres, correos ni
documentos.

| Ruta | Para qué | Respuesta |
|---|---|---|
| `GET /interno/vehiculos/{vehiculo_id}` | Saber si el vehículo existe, su placa y si él y su dueño están aprobados | 200 con el cuerpo de abajo; 404 si no existe |
| `GET /interno/usuarios?id=<uuid>&id=<uuid>` | Saber si existen el conductor (`usuario_id`) y quien autoriza (`autorizado_por_id`) | 200 con la lista de los que existen: `[{"id", "rol", "activo"}]` |

```json
{
  "id": "…",
  "placa": "ABC123",
  "es_visitante": false,
  "estado_verificacion": "aprobado",
  "propietario": { "id": "…", "estado_verificacion": "aprobado" }
}
```

`propietario` es `null` cuando el vehículo no tiene dueño registrado (visitante).

Accesos traduce un 404 de Identidad a su propio 404. Si Identidad no responde, tarda más de 5
segundos o responde algo inesperado, Accesos contesta 503 «El servicio de identidad no está
disponible».

### Si Identidad se cae

| Operación de Accesos | Resultado |
|---|---|
| Registrar una entrada (normal o de visitante) | 503: no se puede comprobar el vehículo ni los usuarios |
| Registrar una salida | Funciona |
| Listar vehículos adentro y buscar un acceso por placa | Funcionan: `accesos` guarda la placa al registrar la entrada |

### Decisiones del servicio

- **No se copian datos.** Las bases solo tienen usuarios de prueba: en la base nueva se siembran
  un administrador y un vigilante.
- **Auditoría propia.** Aprobar o rechazar un usuario o un vehículo se registra en
  `auditoria_identidad` (solo inserción) y se consulta en `GET /api/v1/verificaciones/auditoria`
  (solo administrador). Las trazas anteriores quedan en `auditoria_accesos`: la auditoría no se
  modifica ni se borra.
- **Accesos guarda la placa.** Así las salidas no dependen de Identidad; `vehiculo_id`,
  `usuario_id` y `autorizado_por_id` quedan como identificadores sin llave foránea.
- **`/interno` sin clave por ahora.** Está protegida solo por no publicarse en el gateway, igual
  que la de Parqueadero; la clave entre servicios llega con el paso 7.

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
