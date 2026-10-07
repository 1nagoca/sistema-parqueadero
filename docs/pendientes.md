# Pasos pendientes

Lo que falta para terminar la migración a microservicios y corregir lo que observó el profesor.
El detalle de lo ya hecho y de cómo funciona está en [`arquitectura.md`](arquitectura.md).

## Dónde estamos

| Paso | Estado |
|---|---|
| 1. Gateway + visión con pantalla propia | Hecho |
| 2. Separar Parqueadero con su base de datos | Hecho |
| 3. Separar Identidad y verificación | Hecho |
| 4. Accesos con su base y auditoría | Hecho |
| 5. Corregir diagramas, BPM y documentos | Pendiente |
| 6. Preparar la presentación | Pendiente |
| 7. Endurecer secretos antes de publicar | Pendiente |

## Paso 3 — Separar Identidad y verificación (hecho)

Crear el servicio `backend-identidad` con su propia base de datos. El contrato está en
[`arquitectura.md`](arquitectura.md#servicio-de-identidad-contrato). No se copian datos: las
bases solo tienen usuarios de prueba.

### A. Contrato

- [x] Dejar por escrito la API interna, los claims del token, los nombres y puertos y las
      decisiones del servicio.

### B. Servicio nuevo vacío

- [x] Crear `backend-identidad` (FastAPI, `/health`, Alembic y tests) en el puerto interno 8003.
- [x] Agregar a `docker-compose.yml` el servicio, el contenedor `db-identidad` (base
      `parqueadero_identidad`, puerto 5435 en el host) y un volumen propio para archivos.

### C. Copiar el código de identidad

- [x] Copiar inicio de sesión, registro, usuarios, vehículos, documentos y verificaciones
      (routers, modelos, esquemas y servicios). `backend-core` sigue intacto y atendiendo.
- [x] Migración inicial con `usuarios`, `vehiculos`, `documentos` y `auditoria_identidad`
      (solo inserción, como `auditoria_accesos`).
- [x] La verificación escribe en `auditoria_identidad` y se lee en
      `GET /api/v1/verificaciones/auditoria` (solo administrador).
- [x] Crear la API interna: `GET /interno/vehiculos/{id}` y `GET /interno/usuarios?id=`.
- [x] Copiar los tests de identidad de `test_verificacion.py` al servicio nuevo.

### D. Sembrar admin y vigilante

- [x] Script de siembra que crea un administrador y un vigilante si no existen, con las
      contraseñas tomadas del entorno.

### E. Desacoplar core

- [x] Validar el token por su cuenta, sin consultar la tabla `usuarios`.
- [x] Guardar la `placa` en `accesos` al registrar la entrada; la lista de vehículos adentro y
      la búsqueda por placa dejan de leer `vehiculos`.
- [x] Consultar a identidad por su API interna el vehículo, su dueño y la existencia de
      `usuario_id` y `autorizado_por_id` (hoy son consultas directas a la base).
- [x] Si identidad no responde, rechazar toda entrada con 503 y un mensaje claro; salidas,
      lista y búsqueda siguen funcionando.
- [x] Quitar las llaves foráneas de `accesos` a `usuarios` y `vehiculos` y la de
      `auditoria_accesos.realizado_por_id`: quedan como identificadores sin restricción, igual
      que `zona_id` y `espacio_id`.
- [x] Sustituir identidad por un doble en los tests de accesos.

Entre la parte E y la F el entorno de desarrollo no funciona de punta a punta: el navegador
aún crea usuarios y vehículos en `backend-core` y accesos ya los busca en identidad.

### F. Corte del gateway y borrado en core

- [x] Enviar a identidad `/auth`, `/usuarios`, `/vehiculos`, `/documentos` y `/verificaciones`.
- [x] Apuntar a identidad la validación de sesión de visión.
- [x] Borrar de `backend-core` el código y los tests de identidad, las tablas `documentos`,
      `vehiculos` y `usuarios` (migración reversible) y el volumen `uploads_data`.
- [x] Retirar o adaptar `tests/test_migracion_placa.py` de `backend-core` cuando se borren
      `usuarios` y `vehiculos`.

### G. Cierre y documentación

- [x] Frontend: mostrar en la pantalla de auditoría del administrador las dos fuentes, accesos
      (`/auditoria`) y verificaciones (`/verificaciones/auditoria`).
- [x] Probar el flujo completo en el navegador.
- [x] Actualizar `arquitectura.md`, `README.md`, `AGENTS.md` y `base-de-datos/`.

Las partes B, C, E y F requieren aprobar cambios de esquema o de `docker-compose.yml`.

## Paso 4 — Accesos con su base y auditoría (hecho)

Lo que quedó en `backend-core` es el servicio de Accesos, ahora `backend-accesos`. Se hizo
durante el paso 3:

- [x] Base propia (`parqueadero`) solo con `accesos` y `auditoria_accesos`, sin tablas ni llaves
      foráneas de identidad.
- [x] Auditoría propia de accesos; la de verificaciones pasó a identidad.
- [x] Validar el token por firma y claims y consultar a identidad por su API interna.

Y como cierre:

- [x] Renombrar `backend-core` a `backend-accesos` (carpeta, `docker-compose.yml`, gateway y
      documentación).

## Paso 5 — Corregir diagramas, BPM y documentos

Para que todo coincida con el código real.

- [ ] **BPM por roles:** una calle por rol (estudiante, vigilante, administrador, sistema) con las
      actividades de cada uno, como pidió el profesor.
- [x] **Diagrama de arquitectura:** los 4 microservicios, cada uno con su base de datos, y el
      gateway como entrada única.
- [x] **Diagrama de despliegue:** agregar el gateway y las bases separadas; corregir
      `postgres:15` por `postgres:16`.
- [x] **Mapa de contextos:** ya no hay "Shared Kernel" entre Espacios y Accesos; ahora se hablan
      por API.
- [x] **Capas:** explicar que las capas (routers → services → models) son la organización interna
      de cada microservicio, no la arquitectura global.
- [ ] Actualizar `README.md` y `AGENTS.md` (estructura, comandos y puertos nuevos).
- [ ] Actualizar la colección de Postman si cambia alguna ruta.

## Paso 6 — Preparar la presentación

- [ ] Armar una agenda y repartir los temas para que la exposición sea coherente.
- [ ] Preparar la demostración: registro de estudiante, aprobación del administrador, lectura de
      placa con foto, entrada y salida con el mapa actualizándose en vivo.
- [ ] Demostrar la autonomía: apagar una base de datos y mostrar que el otro servicio sigue
      respondiendo.
- [ ] Confirmar con el profesor el enfoque (una base por microservicio y API Gateway).

## Paso 7 — Endurecer secretos antes de publicar

`SECRET_KEY` (firma los tokens de sesión) y `POSTGRES_PASSWORD` tienen valores de ejemplo
públicos en `.env.example`.

- [ ] Generar un `SECRET_KEY` nuevo (`openssl rand -hex 32`) y ponerlo solo en `.env`, nunca en
      `.env.example`.
- [ ] Cambiar `POSTGRES_PASSWORD` en `.env` por una contraseña larga (si el volumen de la base ya
      existe, recrearlo o cambiarla también dentro de Postgres). Aplica a las tres bases:
      `parqueadero`, `parqueadero_zonas` y `parqueadero_identidad`.
- [ ] Confirmar que `.env.example` conserva solo valores de ejemplo.
- [ ] Pasar a variables de Postman las contraseñas escritas en
      `postman/parqueadero.postman_collection.json` y no reutilizar esas contraseñas.
- [ ] No exponer los puertos de las bases de datos al exterior en `docker-compose.yml`.
- [ ] Confirmar que `CORS_ORIGINS` solo incluye los orígenes reales.

Obligatorio antes de publicarlo en internet o de usarlo con datos reales de estudiantes.

## Mejoras menores detectadas

No bloquean nada, pero conviene arreglarlas.

- [x] Registrar una entrada de un vehículo que ya está adentro responde error 500; debería dar un
      mensaje claro (409).
- [ ] Si falla la compensación de un cupo, solo queda un registro en el log; falta un reintento.
- [ ] La API interna de Parqueadero (`/interno`) solo está protegida por no estar publicada;
      agregar una clave entre servicios.
- [ ] "Zona A - Principal" tiene el contador de cupos desfasado en 1 (6 disponibles, deberían
      ser 7).
- [ ] Probar toda la interfaz en un navegador, incluida la lectura de placas con fotos reales.
- [ ] La lectura de placas la puede usar cualquier usuario con sesión; limitarla a vigilantes y
      administradores.
- [x] Entrada con vehiculo_id inexistente responde 500 en vez de 404/409 (violación de llave foránea; deducido del código, no probado)
- [x] Entrada con usuario_id o autorizado_por_id inexistente responde 500 en vez de 404 (violación de llave foránea a usuarios; deducido del código, no probado)
- [ ] Los índices de las migraciones de identidad y de accesos no están declarados en los modelos (`alembic check`; solo afecta a `--autogenerate`)
- [ ] `deps.py` de identidad responde 500 en vez de 401 si el token trae un `sub` que no es UUID (deducido del código, no probado; accesos y parqueadero ya lo manejan)
- [ ] `POST /vehiculos` con un `usuario_id` que no existe responde 500 por la llave foránea (identidad; deducido, no probado)
- [ ] El frontend no tiene configuración de ESLint, así que `npm run lint` no corre.
- [ ] Un usuario desactivado conserva acceso a accesos y parqueadero hasta que expire su token (8 horas), porque el token se valida sin consultar a identidad.
- [ ] Las placas venezolanas (7 caracteres) no se aceptan: solo se valida el formato colombiano y el campo del formulario permite 6 caracteres.
- [ ] No se valida que quien autoriza una entrada de visitante (`autorizado_por_id`) sea vigilante o administrador.
- [ ] La colección de Postman lleva contraseñas de prueba escritas en el archivo versionado y sus inicios de sesión usan cuentas (`estudiante@uni.edu.co`, entre otras) que pueden no existir ya en identidad.
- [ ] Alinear `.env.example` con los puertos reales: trae `POSTGRES_PORT=5432` y el equipo de desarrollo usa 5433 para la base de accesos.
- [ ] Corregir los comentarios que aún dicen que `backend-core` llama a visión (`backend-vision`) o avisa por `/ws/zonas` (frontend), y el nombre `backend-core` en la colección de Postman.
