"""Estructura inicial del servicio de identidad: extension pgcrypto, enums y las 4 tablas
(usuarios, vehiculos, documentos, auditoria_identidad).

Revision ID: 0001_estructura_inicial
Revises:
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_estructura_inicial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nombre del rol de aplicacion sobre el que se endurecen los permisos de auditoria.
# Ajustar segun el rol real que use backend-identidad para conectarse en cada entorno
# (en Supabase/Neon normalmente no es el rol "postgres"/superusuario).
APP_ROLE = "parqueadero_app"


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    op.execute(sa.text("CREATE TYPE usuario_rol_enum AS ENUM ('estudiante', 'docente', 'administrativo', 'vigilante', 'admin')"))
    op.execute(sa.text("CREATE TYPE vehiculo_tipo_enum AS ENUM ('carro', 'moto', 'bicicleta', 'otro')"))
    op.execute(sa.text("CREATE TYPE verificacion_estado_enum AS ENUM ('pendiente', 'aprobado', 'rechazado')"))
    op.execute(sa.text("CREATE TYPE documento_tipo_enum AS ENUM ('carnet', 'foto_placa', 'tarjeta_propiedad')"))
    op.execute(sa.text("CREATE TYPE auditoria_accion_enum AS ENUM ('creacion', 'actualizacion', 'eliminacion')"))

    op.execute(
        sa.text(
            """
            CREATE TABLE usuarios (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nombre_completo VARCHAR(150) NOT NULL,
                correo_institucional VARCHAR(150) NOT NULL UNIQUE,
                documento_identidad VARCHAR(30) NOT NULL UNIQUE,
                telefono VARCHAR(20),
                rol usuario_rol_enum NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                universidad VARCHAR(150),
                estado_verificacion verificacion_estado_enum NOT NULL DEFAULT 'aprobado',
                motivo_rechazo TEXT,
                consentimiento_datos_en TIMESTAMPTZ,
                activo BOOLEAN NOT NULL DEFAULT true,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE vehiculos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                placa VARCHAR(10) NOT NULL UNIQUE,
                tipo_vehiculo vehiculo_tipo_enum NOT NULL,
                marca VARCHAR(50),
                modelo VARCHAR(50),
                color VARCHAR(30),
                usuario_id UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
                es_visitante BOOLEAN NOT NULL DEFAULT false,
                estado_verificacion verificacion_estado_enum NOT NULL DEFAULT 'aprobado',
                motivo_rechazo TEXT,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_vehiculos_placa_mayusculas CHECK (placa = upper(placa)),
                CONSTRAINT ck_vehiculos_propietario_o_visitante
                    CHECK (usuario_id IS NOT NULL OR es_visitante = true)
            )
            """
        )
    )
    op.execute(sa.text("CREATE INDEX idx_vehiculos_usuario_id ON vehiculos (usuario_id)"))

    op.execute(
        sa.text(
            """
            CREATE TABLE documentos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                vehiculo_id UUID REFERENCES vehiculos(id) ON DELETE CASCADE,
                tipo documento_tipo_enum NOT NULL,
                ruta_archivo VARCHAR(255) NOT NULL,
                content_type VARCHAR(50) NOT NULL,
                tamano_bytes INTEGER NOT NULL,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_documentos_vehiculo_segun_tipo CHECK (
                    (tipo = 'carnet' AND vehiculo_id IS NULL)
                    OR (tipo <> 'carnet' AND vehiculo_id IS NOT NULL)
                )
            )
            """
        )
    )
    op.execute(sa.text("CREATE INDEX idx_documentos_usuario_id ON documentos (usuario_id)"))
    op.execute(sa.text("CREATE INDEX idx_documentos_vehiculo_id ON documentos (vehiculo_id)"))

    op.execute(
        sa.text(
            """
            CREATE TABLE auditoria_identidad (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tabla_afectada VARCHAR(50) NOT NULL,
                registro_id UUID NOT NULL,
                accion auditoria_accion_enum NOT NULL,
                valores_anteriores JSONB,
                valores_nuevos JSONB,
                realizado_por_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
                motivo TEXT,
                fecha_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
                ip_origen VARCHAR(45)
            )
            """
        )
    )
    op.execute(
        sa.text("CREATE INDEX idx_auditoria_identidad_registro ON auditoria_identidad (tabla_afectada, registro_id)")
    )
    op.execute(sa.text("CREATE INDEX idx_auditoria_identidad_fecha_hora ON auditoria_identidad (fecha_hora)"))

    # La tabla de auditoria es append-only por permisos de BD, no solo por convencion.
    # Se aplica solo si el rol de aplicacion ya existe (permite correr esta migracion antes de
    # aprovisionar el rol en un entorno nuevo).
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    EXECUTE 'REVOKE UPDATE, DELETE ON auditoria_identidad FROM {APP_ROLE}';
                END IF;
            END$$;
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS auditoria_identidad"))
    op.execute(sa.text("DROP TABLE IF EXISTS documentos"))
    op.execute(sa.text("DROP TABLE IF EXISTS vehiculos"))
    op.execute(sa.text("DROP TABLE IF EXISTS usuarios"))

    op.execute(sa.text("DROP TYPE IF EXISTS auditoria_accion_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS documento_tipo_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS verificacion_estado_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS vehiculo_tipo_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS usuario_rol_enum"))
