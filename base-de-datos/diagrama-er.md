# Diagrama entidad-relación

Se visualiza directamente en GitHub (Mermaid). Para exportarlo a PostgreSQL, MySQL u otro motor, usa [`diagrama-er.dbml`](diagrama-er.dbml) en <https://dbdiagram.io/d>.

```mermaid
erDiagram
    usuarios ||--o{ vehiculos : "es dueño de"
    usuarios ||--o{ documentos : "sube"
    vehiculos ||--o{ documentos : "tiene soporte"
    usuarios ||--o{ accesos : "ingresa"
    usuarios ||--o{ accesos : "autoriza visitante"
    vehiculos ||--o{ accesos : "registra"
    zonas ||--o{ espacios : "contiene"
    zonas ||--o{ accesos : "recibe"
    espacios |o--o{ accesos : "ocupa"
    usuarios ||--o{ auditoria_accesos : "realiza"

    usuarios {
        uuid id PK
        varchar nombre_completo
        varchar correo_institucional UK
        varchar documento_identidad UK
        varchar telefono
        enum rol
        varchar hashed_password
        boolean activo
        varchar universidad
        enum estado_verificacion
        text motivo_rechazo
        timestamptz consentimiento_datos_en
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
    accesos {
        uuid id PK
        uuid vehiculo_id FK
        uuid usuario_id FK
        uuid zona_id FK
        uuid espacio_id FK
        enum tipo_acceso
        timestamptz fecha_hora_entrada
        timestamptz fecha_hora_salida
        int duracion_minutos
        uuid autorizado_por_id FK
        text justificacion
        boolean placa_detectada_por_alpr
        numeric confianza_alpr
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
    auditoria_accesos {
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
