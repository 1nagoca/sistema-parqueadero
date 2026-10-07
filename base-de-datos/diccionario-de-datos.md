# Diccionario de datos — Parqueadero UFPS

Motor: PostgreSQL 16. Las llaves primarias son `uuid` generados con `gen_random_uuid()`. Todas las fechas son `timestamptz`.

Hay **una base de datos por microservicio**:

| Base de datos | Servicio | Tablas | Migraciones |
|---|---|---|---|
| `parqueadero_identidad` | `backend-identidad` | `usuarios`, `vehiculos`, `documentos`, `auditoria_identidad` | `backend-identidad/alembic/versions` (0001) |
| `parqueadero` | `backend-accesos` | `accesos`, `auditoria_accesos` | `backend-accesos/alembic/versions` (0001 a 0005) |
| `parqueadero_zonas` | `backend-parqueadero` | `zonas`, `espacios` | `backend-parqueadero/alembic/versions` (0001) |

Entre bases no hay llaves foráneas. `accesos` y `auditoria_accesos` guardan identificadores de vehículos y usuarios (base de identidad) y de zonas y espacios (base de parqueadero); la consistencia la cuida el código (ver `docs/arquitectura.md`).

## Resumen de tablas

| Tabla | Base | Propósito |
|---|---|---|
| `usuarios` | `parqueadero_identidad` | Personas del sistema (estudiantes, docentes, administrativos, vigilantes, admin) |
| `vehiculos` | `parqueadero_identidad` | Vehículos registrados, de un usuario o de un visitante |
| `documentos` | `parqueadero_identidad` | Archivos de soporte para verificar estudiantes y vehículos |
| `auditoria_identidad` | `parqueadero_identidad` | Bitácora de verificaciones (solo se agrega, nunca se modifica ni se borra) |
| `accesos` | `parqueadero` | Entradas y salidas de vehículos |
| `auditoria_accesos` | `parqueadero` | Bitácora de accesos (solo se agrega, nunca se modifica ni se borra) |
| `zonas` | `parqueadero_zonas` | Zonas del parqueadero y sus cupos en tiempo real |
| `espacios` | `parqueadero_zonas` | Puestos individuales dentro de una zona |

## Relaciones

Llaves foráneas, siempre dentro de una misma base:

| Origen | Destino | Cardinalidad | Al borrar |
|---|---|---|---|
| `vehiculos.usuario_id` | `usuarios.id` | muchos a uno (opcional si es visitante) | RESTRICT |
| `documentos.usuario_id` | `usuarios.id` | muchos a uno | CASCADE |
| `documentos.vehiculo_id` | `vehiculos.id` | muchos a uno (opcional) | CASCADE |
| `auditoria_identidad.realizado_por_id` | `usuarios.id` | muchos a uno | RESTRICT |
| `espacios.zona_id` | `zonas.id` | muchos a uno | RESTRICT |

Referencias a otra base, sin llave foránea:

| Origen | Destino | Cardinalidad |
|---|---|---|
| `accesos.vehiculo_id` | `vehiculos.id` (identidad) | muchos a uno |
| `accesos.usuario_id` | `usuarios.id` (identidad) | muchos a uno (opcional) |
| `accesos.autorizado_por_id` | `usuarios.id` (identidad) | muchos a uno (opcional) |
| `auditoria_accesos.realizado_por_id` | `usuarios.id` (identidad) | muchos a uno |
| `accesos.zona_id` | `zonas.id` (parqueadero) | muchos a uno |
| `accesos.espacio_id` | `espacios.id` (parqueadero) | muchos a uno (opcional) |

## Base `parqueadero_identidad`

### usuarios

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `nombre_completo` | varchar(150) | No | | Nombre y apellidos |
| `correo_institucional` | varchar(150) | No | | Único; sirve para iniciar sesión |
| `documento_identidad` | varchar(30) | No | | Único |
| `telefono` | varchar(20) | Sí | | |
| `rol` | `usuario_rol_enum` | No | | estudiante, docente, administrativo, vigilante, admin |
| `hashed_password` | varchar(255) | No | | Contraseña cifrada con bcrypt, nunca en texto plano |
| `universidad` | varchar(150) | Sí | | Universidad declarada en el autorregistro |
| `estado_verificacion` | `verificacion_estado_enum` | No | `aprobado` | pendiente, aprobado, rechazado |
| `motivo_rechazo` | text | Sí | | Razón si fue rechazado |
| `consentimiento_datos_en` | timestamptz | Sí | | Cuándo aceptó el tratamiento de datos |
| `activo` | boolean | No | `true` | Permite deshabilitar sin borrar |
| `creado_en` | timestamptz | No | `now()` | |
| `actualizado_en` | timestamptz | No | `now()` | |

### vehiculos

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `placa` | varchar(10) | No | | Única, siempre en mayúsculas |
| `tipo_vehiculo` | `vehiculo_tipo_enum` | No | | carro, moto, bicicleta, otro |
| `marca` | varchar(50) | Sí | | |
| `modelo` | varchar(50) | Sí | | |
| `color` | varchar(30) | Sí | | |
| `usuario_id` | uuid | Sí | | FK a `usuarios`; dueño del vehículo |
| `es_visitante` | boolean | No | `false` | Vehículo de visitante sin dueño registrado |
| `estado_verificacion` | `verificacion_estado_enum` | No | `aprobado` | |
| `motivo_rechazo` | text | Sí | | |
| `creado_en` | timestamptz | No | `now()` | |

Restricciones: `ck_vehiculos_placa_mayusculas` (placa = upper(placa)); `ck_vehiculos_propietario_o_visitante` (tiene dueño o es visitante). Índice en `usuario_id`.

### documentos

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `usuario_id` | uuid | No | | FK a `usuarios`; quien subió el archivo |
| `vehiculo_id` | uuid | Sí | | FK a `vehiculos`; vacío solo para el carnet |
| `tipo` | `documento_tipo_enum` | No | | carnet, foto_placa, tarjeta_propiedad |
| `ruta_archivo` | varchar(255) | No | | Ruta en el volumen privado `identidad_uploads` |
| `content_type` | varchar(50) | No | | Tipo MIME |
| `tamano_bytes` | integer | No | | |
| `creado_en` | timestamptz | No | `now()` | |

Restricción: `ck_documentos_vehiculo_segun_tipo` (el carnet no lleva vehículo; los demás sí). Índices en `usuario_id` y `vehiculo_id`. Los archivos son datos personales y nunca se sirven como estáticos.

### auditoria_identidad

Bitácora de aprobar o rechazar usuarios y vehículos. Tabla **append-only**: no se actualiza ni se borra. La migración además quita `UPDATE` y `DELETE` al rol de aplicación `parqueadero_app` cuando ese rol existe.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `tabla_afectada` | varchar(50) | No | | Tabla que cambió (`usuarios` o `vehiculos`) |
| `registro_id` | uuid | No | | Registro que cambió |
| `accion` | `auditoria_accion_enum` | No | | creacion, actualizacion, eliminacion |
| `valores_anteriores` | jsonb | Sí | | |
| `valores_nuevos` | jsonb | Sí | | |
| `realizado_por_id` | uuid | No | | FK a `usuarios`; el administrador que decidió |
| `motivo` | text | Sí | | Motivo del rechazo |
| `fecha_hora` | timestamptz | No | `now()` | |
| `ip_origen` | varchar(45) | Sí | | IPv4 o IPv6 |

Índices en `fecha_hora` y en `(tabla_afectada, registro_id)`.

## Base `parqueadero` (accesos)

### accesos

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `vehiculo_id` | uuid | No | | Id del vehículo en la base de identidad (sin FK) |
| `placa` | varchar(10) | No | | Copia de la placa al registrar la entrada, en mayúsculas |
| `usuario_id` | uuid | Sí | | Id de quien ingresa, en la base de identidad (sin FK) |
| `zona_id` | uuid | No | | Id de la zona en la base `parqueadero_zonas` (sin FK) |
| `espacio_id` | uuid | Sí | | Id del espacio en la base `parqueadero_zonas` (sin FK) |
| `tipo_acceso` | `acceso_tipo_enum` | No | `normal` | normal, visitante |
| `fecha_hora_entrada` | timestamptz | No | `now()` | |
| `fecha_hora_salida` | timestamptz | Sí | | Nula mientras el vehículo sigue dentro |
| `duracion_minutos` | integer | Sí | | Se calcula al registrar la salida |
| `autorizado_por_id` | uuid | Sí | | Id de quien autorizó al visitante, en la base de identidad (sin FK) |
| `justificacion` | text | Sí | | Motivo del acceso de visitante |
| `placa_detectada_por_alpr` | boolean | No | `false` | La placa se leyó automáticamente |
| `confianza_alpr` | numeric(5,2) | Sí | | Confianza de la lectura de placa |
| `creado_en` | timestamptz | No | `now()` | |

Restricciones: `ck_accesos_placa_mayusculas` (placa = upper(placa)); `ck_accesos_salida_posterior_entrada`; `ck_accesos_visitante_requiere_autorizacion` (un visitante exige `autorizado_por_id` y justificación); índice único parcial `uq_accesos_vehiculo_activo` (un vehículo no puede tener dos accesos sin salida). Índices en `usuario_id` y `zona_id`.

La placa se guarda aquí para que la lista de vehículos adentro, la búsqueda por placa y las salidas funcionen aunque el servicio de identidad no responda.

### auditoria_accesos

Bitácora de entradas y salidas. Tabla **append-only**: no se actualiza ni se borra. La migración además quita `UPDATE` y `DELETE` al rol de aplicación `parqueadero_app` cuando ese rol existe. Conserva las trazas de verificación anteriores a la separación de identidad.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `tabla_afectada` | varchar(50) | No | | Tabla que cambió |
| `registro_id` | uuid | No | | Registro que cambió |
| `accion` | `auditoria_accion_enum` | No | | creacion, actualizacion, eliminacion |
| `valores_anteriores` | jsonb | Sí | | |
| `valores_nuevos` | jsonb | Sí | | |
| `realizado_por_id` | uuid | No | | Id del usuario en la base de identidad (sin FK) |
| `motivo` | text | Sí | | |
| `fecha_hora` | timestamptz | No | `now()` | |
| `ip_origen` | varchar(45) | Sí | | IPv4 o IPv6 |

Índices en `fecha_hora` y en `(tabla_afectada, registro_id)`.

## Base `parqueadero_zonas`

### zonas

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `nombre` | varchar(100) | No | | Único |
| `ubicacion_descripcion` | text | Sí | | |
| `capacidad_total` | integer | No | | Mayor que 0 |
| `cupos_disponibles` | integer | No | | Entre 0 y `capacidad_total` |
| `activa` | boolean | No | `true` | |
| `creado_en` | timestamptz | No | `now()` | |
| `actualizado_en` | timestamptz | No | `now()` | |

Restricciones: `ck_zonas_capacidad_positiva`, `ck_zonas_cupos_en_rango`.

### espacios

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `zona_id` | uuid | No | | FK a `zonas` |
| `codigo` | varchar(20) | No | | Código del puesto, único dentro de la zona |
| `estado` | `espacio_estado_enum` | No | `libre` | libre, ocupado, reservado, mantenimiento |
| `tipo_espacio` | varchar(20) | Sí | | |
| `creado_en` | timestamptz | No | `now()` | |
| `actualizado_en` | timestamptz | No | `now()` | |

Restricciones: único `(zona_id, codigo)`. Índice en `zona_id`.

## Enumeraciones

| Enum | Base | Valores |
|---|---|---|
| `usuario_rol_enum` | `parqueadero_identidad` | estudiante, docente, administrativo, vigilante, admin |
| `vehiculo_tipo_enum` | `parqueadero_identidad` | carro, moto, bicicleta, otro |
| `verificacion_estado_enum` | `parqueadero_identidad` | pendiente, aprobado, rechazado |
| `documento_tipo_enum` | `parqueadero_identidad` | carnet, foto_placa, tarjeta_propiedad |
| `auditoria_accion_enum` | `parqueadero_identidad` y `parqueadero` | creacion, actualizacion, eliminacion |
| `acceso_tipo_enum` | `parqueadero` | normal, visitante |
| `espacio_estado_enum` | `parqueadero_zonas` | libre, ocupado, reservado, mantenimiento |
