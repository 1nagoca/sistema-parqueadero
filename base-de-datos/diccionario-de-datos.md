# Diccionario de datos — Parqueadero UFPS

Motor: PostgreSQL 16. Las llaves primarias son `uuid` generados con `gen_random_uuid()`. Todas las fechas son `timestamptz`.
Fuente: migraciones `backend-core/alembic/versions` (0001 estructura inicial, 0002 verificación de estudiantes).

## Resumen de tablas

| Tabla | Propósito |
|---|---|
| `usuarios` | Personas del sistema (estudiantes, docentes, administrativos, vigilantes, admin) |
| `vehiculos` | Vehículos registrados, de un usuario o de un visitante |
| `zonas` | Zonas del parqueadero y sus cupos en tiempo real |
| `espacios` | Puestos individuales dentro de una zona |
| `accesos` | Entradas y salidas de vehículos |
| `documentos` | Archivos de soporte para verificar estudiantes y vehículos |
| `auditoria_accesos` | Bitácora de cambios (solo se agrega, nunca se modifica ni se borra) |

## Relaciones

| Origen | Destino | Cardinalidad | Al borrar |
|---|---|---|---|
| `vehiculos.usuario_id` | `usuarios.id` | muchos a uno (opcional si es visitante) | RESTRICT |
| `espacios.zona_id` | `zonas.id` | muchos a uno | RESTRICT |
| `accesos.vehiculo_id` | `vehiculos.id` | muchos a uno | RESTRICT |
| `accesos.usuario_id` | `usuarios.id` | muchos a uno (opcional) | RESTRICT |
| `accesos.zona_id` | `zonas.id` | muchos a uno | RESTRICT |
| `accesos.espacio_id` | `espacios.id` | muchos a uno (opcional) | RESTRICT |
| `accesos.autorizado_por_id` | `usuarios.id` | muchos a uno (opcional) | RESTRICT |
| `documentos.usuario_id` | `usuarios.id` | muchos a uno | CASCADE |
| `documentos.vehiculo_id` | `vehiculos.id` | muchos a uno (opcional) | CASCADE |
| `auditoria_accesos.realizado_por_id` | `usuarios.id` | muchos a uno | RESTRICT |

## usuarios

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `nombre_completo` | varchar(150) | No | | Nombre y apellidos |
| `correo_institucional` | varchar(150) | No | | Único; sirve para iniciar sesión |
| `documento_identidad` | varchar(30) | No | | Único |
| `telefono` | varchar(20) | Sí | | |
| `rol` | `usuario_rol_enum` | No | | estudiante, docente, administrativo, vigilante, admin |
| `hashed_password` | varchar(255) | No | | Contraseña cifrada con bcrypt, nunca en texto plano |
| `activo` | boolean | No | `true` | Permite deshabilitar sin borrar |
| `universidad` | varchar(150) | Sí | | Universidad declarada en el autorregistro |
| `estado_verificacion` | `verificacion_estado_enum` | No | `aprobado` | pendiente, aprobado, rechazado |
| `motivo_rechazo` | text | Sí | | Razón si fue rechazado |
| `consentimiento_datos_en` | timestamptz | Sí | | Cuándo aceptó el tratamiento de datos |
| `creado_en` | timestamptz | No | `now()` | |
| `actualizado_en` | timestamptz | No | `now()` | |

## vehiculos

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

## zonas

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

## espacios

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

## accesos

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `vehiculo_id` | uuid | No | | FK a `vehiculos` |
| `usuario_id` | uuid | Sí | | FK a `usuarios`; quien ingresa |
| `zona_id` | uuid | No | | FK a `zonas` |
| `espacio_id` | uuid | Sí | | FK a `espacios` |
| `tipo_acceso` | `acceso_tipo_enum` | No | `normal` | normal, visitante |
| `fecha_hora_entrada` | timestamptz | No | `now()` | |
| `fecha_hora_salida` | timestamptz | Sí | | Nula mientras el vehículo sigue dentro |
| `duracion_minutos` | integer | Sí | | Se calcula al registrar la salida |
| `autorizado_por_id` | uuid | Sí | | FK a `usuarios`; quien autorizó al visitante |
| `justificacion` | text | Sí | | Motivo del acceso de visitante |
| `placa_detectada_por_alpr` | boolean | No | `false` | La placa se leyó automáticamente |
| `confianza_alpr` | numeric(5,2) | Sí | | Confianza de la lectura de placa |
| `creado_en` | timestamptz | No | `now()` | |

Restricciones: `ck_accesos_salida_posterior_entrada`; `ck_accesos_visitante_requiere_autorizacion` (un visitante exige `autorizado_por_id` y justificación); índice único parcial `uq_accesos_vehiculo_activo` (un vehículo no puede tener dos accesos sin salida). Índices en `usuario_id` y `zona_id`.

## documentos

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `usuario_id` | uuid | No | | FK a `usuarios`; quien subió el archivo |
| `vehiculo_id` | uuid | Sí | | FK a `vehiculos`; vacío solo para el carnet |
| `tipo` | `documento_tipo_enum` | No | | carnet, foto_placa, tarjeta_propiedad |
| `ruta_archivo` | varchar(255) | No | | Ruta en el volumen privado de uploads |
| `content_type` | varchar(50) | No | | Tipo MIME |
| `tamano_bytes` | integer | No | | |
| `creado_en` | timestamptz | No | `now()` | |

Restricción: `ck_documentos_vehiculo_segun_tipo` (el carnet no lleva vehículo; los demás sí). Los archivos son datos personales y nunca se sirven como estáticos.

## auditoria_accesos

Tabla **append-only**: no se actualiza ni se borra.

| Columna | Tipo | Nulo | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | uuid | No | `gen_random_uuid()` | PK |
| `tabla_afectada` | varchar(50) | No | | Tabla que cambió |
| `registro_id` | uuid | No | | Registro que cambió |
| `accion` | `auditoria_accion_enum` | No | | creacion, actualizacion, eliminacion |
| `valores_anteriores` | jsonb | Sí | | |
| `valores_nuevos` | jsonb | Sí | | |
| `realizado_por_id` | uuid | No | | FK a `usuarios` |
| `motivo` | text | Sí | | |
| `fecha_hora` | timestamptz | No | `now()` | |
| `ip_origen` | varchar(45) | Sí | | IPv4 o IPv6 |

Índices en `fecha_hora` y en `(tabla_afectada, registro_id)`.

## Enumeraciones

| Enum | Valores |
|---|---|
| `usuario_rol_enum` | estudiante, docente, administrativo, vigilante, admin |
| `vehiculo_tipo_enum` | carro, moto, bicicleta, otro |
| `acceso_tipo_enum` | normal, visitante |
| `espacio_estado_enum` | libre, ocupado, reservado, mantenimiento |
| `verificacion_estado_enum` | pendiente, aprobado, rechazado |
| `documento_tipo_enum` | carnet, foto_placa, tarjeta_propiedad |
| `auditoria_accion_enum` | creacion, actualizacion, eliminacion |
