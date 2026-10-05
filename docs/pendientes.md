# Pasos pendientes

Lo que falta para terminar la migración a microservicios y corregir lo que observó el profesor.
El detalle de lo ya hecho y de cómo funciona está en [`arquitectura.md`](arquitectura.md).

## Dónde estamos

| Paso | Estado |
|---|---|
| 1. Gateway + visión con pantalla propia | Hecho |
| 2. Separar Parqueadero con su base de datos | Hecho |
| 3. Separar Identidad y verificación | Pendiente |
| 4. Accesos con su base y auditoría | Pendiente |
| 5. Corregir diagramas, BPM y documentos | Pendiente |
| 6. Preparar la presentación | Pendiente |

## Paso 3 — Separar Identidad y verificación

Crear el servicio `backend-identidad` con su propia base de datos.

- [ ] Mover a ese servicio: inicio de sesión, registro, usuarios, vehículos, documentos y
      verificaciones (routers, modelos, esquemas y servicios).
- [ ] Mover las tablas `usuarios`, `vehiculos` y `documentos` a una base nueva, con su migración
      inicial y copiando los datos actuales (igual que se hizo con zonas y espacios).
- [ ] Mover el volumen de archivos subidos (`uploads_data`) al servicio nuevo.
- [ ] Agregar las rutas al gateway: `/auth`, `/usuarios`, `/vehiculos`, `/documentos`,
      `/verificaciones`.
- [ ] Cambiar en el gateway la validación de sesión de visión para que apunte al servicio nuevo.
- [ ] Pasar sus tests (`test_verificacion.py`) al servicio nuevo.

Requiere aprobar el cambio de esquema.

## Paso 4 — Accesos con su base y auditoría

Lo que queda en `backend-core` pasa a ser el servicio de Accesos.

- [ ] Renombrar `backend-core` a `backend-accesos` (carpeta, `docker-compose.yml`, gateway).
- [ ] Quitar de `accesos` las llaves foráneas a `usuarios` y `vehiculos`: quedan como
      identificadores sin restricción, igual que `zona_id` y `espacio_id`.
- [ ] Quitar la llave foránea de `auditoria_accesos.realizado_por_id` a `usuarios`.
- [ ] Crear en Identidad una API interna para que Accesos consulte un vehículo por placa y si el
      vehículo y su dueño están aprobados (hoy se hace con una consulta directa a la base).
- [ ] Decidir dónde se audita la verificación de estudiantes: hoy escribe en la misma tabla de
      auditoría que los accesos.
- [ ] Hacer que Accesos valide el token por su cuenta, sin consultar la tabla de usuarios.

Requiere aprobar el cambio de esquema.

## Paso 5 — Corregir diagramas, BPM y documentos

Para que todo coincida con el código real.

- [ ] **BPM por roles:** una calle por rol (estudiante, vigilante, administrador, sistema) con las
      actividades de cada uno, como pidió el profesor.
- [ ] **Diagrama de arquitectura:** los 4 microservicios, cada uno con su base de datos, y el
      gateway como entrada única.
- [ ] **Diagrama de despliegue:** agregar el gateway y las bases separadas; corregir
      `postgres:15` por `postgres:16`.
- [ ] **Mapa de contextos:** ya no hay "Shared Kernel" entre Espacios y Accesos; ahora se hablan
      por API.
- [ ] **Capas:** explicar que las capas (routers → services → models) son la organización interna
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

## Mejoras menores detectadas

No bloquean nada, pero conviene arreglarlas.

- [ ] Registrar una entrada de un vehículo que ya está adentro responde error 500; debería dar un
      mensaje claro (409).
- [ ] Si falla la compensación de un cupo, solo queda un registro en el log; falta un reintento.
- [ ] La API interna de Parqueadero (`/interno`) solo está protegida por no estar publicada;
      agregar una clave entre servicios.
- [ ] "Zona A - Principal" tiene el contador de cupos desfasado en 1 (6 disponibles, deberían
      ser 7).
- [ ] Probar toda la interfaz en un navegador, incluida la lectura de placas con fotos reales.
- [ ] La lectura de placas la puede usar cualquier usuario con sesión; limitarla a vigilantes y
      administradores.
