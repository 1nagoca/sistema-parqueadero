# Diagrama entidad-relación

Hay una base de datos por microservicio, así que hay un diagrama por base. Entre bases no hay llaves foráneas: lo que una guarda de otra es solo un identificador, y la consistencia la cuida el código (ver [`docs/arquitectura.md`](../docs/arquitectura.md)).

Se visualiza directamente en GitHub (Mermaid). Para exportarlo a PostgreSQL, MySQL u otro motor, usa [`diagrama-er.dbml`](diagrama-er.dbml) en <https://dbdiagram.io/d>.

## Identidad — base `parqueadero_identidad`

```mermaid
erDiagram
    usuarios ||--o{ vehiculos : "es dueño de"
    usuarios ||--o{ documentos : "sube"
    vehiculos ||--o{ documentos : "tiene soporte"
    usuarios ||--o{ auditoria_identidad : "realiza"

    usuarios {
        uuid id PK
        varchar nombre_completo
        varchar correo_institucional UK
        varchar documento_identidad UK
        varchar telefono
        enum rol
        varchar hashed_password
        varchar universidad
        enum estado_verificacion
        text motivo_rechazo
        timestamptz consentimiento_datos_en
        boolean activo
        timestamptz creado_en
        timestamptz actualizado_en
    }
    vehiculos {
        uuid id PK
        varchar placa UK
        enum tipo_vehiculo
        varchar marca
        varchar modelo
        varchar color
        uuid usuario_id FK
        boolean es_visitante
        enum estado_verificacion
        text motivo_rechazo
        timestamptz creado_en
    }
    documentos {
        uuid id PK
        uuid usuario_id FK
        uuid vehiculo_id FK
        enum tipo
        varchar ruta_archivo
        varchar content_type
        int tamano_bytes
        timestamptz creado_en
    }
    auditoria_identidad {
        uuid id PK
        varchar tabla_afectada
        uuid registro_id
        enum accion
        jsonb valores_anteriores
        jsonb valores_nuevos
        uuid realizado_por_id FK
        text motivo
        timestamptz fecha_hora
        varchar ip_origen
    }
```

## Accesos — base `parqueadero`

Las dos tablas no tienen llaves foráneas: `vehiculo_id`, `usuario_id`, `autorizado_por_id` y `realizado_por_id` son identificadores de la base de identidad, y `zona_id` y `espacio_id`, de la de parqueadero.

```mermaid
erDiagram
    accesos {
        uuid id PK
        uuid vehiculo_id
        varchar placa
        uuid usuario_id
        uuid zona_id
        uuid espacio_id
        enum tipo_acceso
        timestamptz fecha_hora_entrada
        timestamptz fecha_hora_salida
        int duracion_minutos
        uuid autorizado_por_id
        text justificacion
        boolean placa_detectada_por_alpr
        numeric confianza_alpr
        timestamptz creado_en
    }
    auditoria_accesos {
        uuid id PK
        varchar tabla_afectada
        uuid registro_id
        enum accion
        jsonb valores_anteriores
        jsonb valores_nuevos
        uuid realizado_por_id
        text motivo
        timestamptz fecha_hora
        varchar ip_origen
    }
```

## Parqueadero — base `parqueadero_zonas`

```mermaid
erDiagram
    zonas ||--o{ espacios : "contiene"

    zonas {
        uuid id PK
        varchar nombre UK
        text ubicacion_descripcion
        int capacidad_total
        int cupos_disponibles
        boolean activa
        timestamptz creado_en
        timestamptz actualizado_en
    }
    espacios {
        uuid id PK
        uuid zona_id FK
        varchar codigo
        enum estado
        varchar tipo_espacio
        timestamptz creado_en
        timestamptz actualizado_en
    }
```

## Referencias entre bases (sin llave foránea)

| Columna | Apunta a | Base de destino |
|---|---|---|
| `accesos.vehiculo_id` | `vehiculos.id` | `parqueadero_identidad` |
| `accesos.usuario_id` | `usuarios.id` | `parqueadero_identidad` |
| `accesos.autorizado_por_id` | `usuarios.id` | `parqueadero_identidad` |
| `auditoria_accesos.realizado_por_id` | `usuarios.id` | `parqueadero_identidad` |
| `accesos.zona_id` | `zonas.id` | `parqueadero_zonas` |
| `accesos.espacio_id` | `espacios.id` | `parqueadero_zonas` |
