"""Estructura inicial: extension pgcrypto, enums y las 5 tablas del dominio
(usuarios, vehiculos, zonas, espacios, accesos, auditoria_accesos) con las
restricciones que aplican RN-01 a RN-04.

Revision ID: 0001_estructura_inicial
Revises:
Create Date: 2026-09-21

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_estructura_inicial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nombre del rol de aplicacion sobre el que se endurecen los permisos de auditoria (RN-04).
# Ajustar segun el rol real que use backend-core para conectarse en cada entorno
# (en Supabase/Neon normalmente no es el rol "postgres"/superusuario).
APP_ROLE = "parqueadero_app"


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    op.execute(sa.text("CREATE TYPE usuario_rol_enum AS ENUM ('estudiante', 'docente', 'administrativo', 'vigilante', 'admin')"))
    op.execute(sa.text("CREATE TYPE vehiculo_tipo_enum AS ENUM ('carro', 'moto', 'bicicleta', 'otro')"))
    op.execute(sa.text("CREATE TYPE espacio_estado_enum AS ENUM ('libre', 'ocupado', 'reservado', 'mantenimiento')"))
    op.execute(sa.text("CREATE TYPE acceso_tipo_enum AS ENUM ('normal', 'visitante')"))
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
            CREATE TABLE zonas (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nombre VARCHAR(100) NOT NULL UNIQUE,
                ubicacion_descripcion TEXT,
                capacidad_total INTEGER NOT NULL,
                cupos_disponibles INTEGER NOT NULL,
                activa BOOLEAN NOT NULL DEFAULT true,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_zonas_capacidad_positiva CHECK (capacidad_total > 0),
                CONSTRAINT ck_zonas_cupos_en_rango
                    CHECK (cupos_disponibles >= 0 AND cupos_disponibles <= capacidad_total)
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE espacios (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                zona_id UUID NOT NULL REFERENCES zonas(id) ON DELETE RESTRICT,
                codigo VARCHAR(20) NOT NULL,
                estado espacio_estado_enum NOT NULL DEFAULT 'libre',
                tipo_espacio VARCHAR(20),
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_espacios_zona_codigo UNIQUE (zona_id, codigo)
            )
            """
        )
    )
    op.execute(sa.text("CREATE INDEX idx_espacios_zona_id ON espacios (zona_id)"))

    op.execute(
        sa.text(
            """
            CREATE TABLE accesos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                vehiculo_id UUID NOT NULL REFERENCES vehiculos(id) ON DELETE RESTRICT,
                usuario_id UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
                zona_id UUID NOT NULL REFERENCES zonas(id) ON DELETE RESTRICT,
                espacio_id UUID REFERENCES espacios(id) ON DELETE RESTRICT,
                tipo_acceso acceso_tipo_enum NOT NULL DEFAULT 'normal',
                fecha_hora_entrada TIMESTAMPTZ NOT NULL DEFAULT now(),
                fecha_hora_salida TIMESTAMPTZ,
                duracion_minutos INTEGER,
                autorizado_por_id UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
                justificacion TEXT,
                placa_detectada_por_alpr BOOLEAN NOT NULL DEFAULT false,
                confianza_alpr NUMERIC(5, 2),
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_accesos_salida_posterior_entrada
                    CHECK (fecha_hora_salida IS NULL OR fecha_hora_salida > fecha_hora_entrada),
                CONSTRAINT ck_accesos_visitante_requiere_autorizacion CHECK (
                    tipo_acceso <> 'visitante'
                    OR (autorizado_por_id IS NOT NULL AND justificacion IS NOT NULL AND justificacion <> '')
                )
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_accesos_vehiculo_activo ON accesos (vehiculo_id) "
            "WHERE fecha_hora_salida IS NULL"
        )
    )
    op.execute(sa.text("CREATE INDEX idx_accesos_zona_id ON accesos (zona_id)"))
    op.execute(sa.text("CREATE INDEX idx_accesos_usuario_id ON accesos (usuario_id)"))

    op.execute(
        sa.text(
            """
            CREATE TABLE auditoria_accesos (
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
        sa.text("CREATE INDEX idx_auditoria_accesos_registro ON auditoria_accesos (tabla_afectada, registro_id)")
    )
    op.execute(sa.text("CREATE INDEX idx_auditoria_accesos_fecha_hora ON auditoria_accesos (fecha_hora)"))

    # RN-04: la tabla de auditoria es append-only por permisos de BD, no solo por convencion.
    # Las salidas de accesos siempre son UPDATE (se fija fecha_hora_salida), nunca DELETE.
    # Se aplica solo si el rol de aplicacion ya existe (permite correr esta migracion antes de
    # aprovisionar el rol en un entorno nuevo).
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    EXECUTE 'REVOKE UPDATE, DELETE ON auditoria_accesos FROM {APP_ROLE}';
                    EXECUTE 'REVOKE DELETE ON accesos FROM {APP_ROLE}';
                END IF;
            END$$;
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS auditoria_accesos"))
    op.execute(sa.text("DROP TABLE IF EXISTS accesos"))
    op.execute(sa.text("DROP TABLE IF EXISTS espacios"))
    op.execute(sa.text("DROP TABLE IF EXISTS zonas"))
    op.execute(sa.text("DROP TABLE IF EXISTS vehiculos"))
    op.execute(sa.text("DROP TABLE IF EXISTS usuarios"))

    op.execute(sa.text("DROP TYPE IF EXISTS auditoria_accion_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS acceso_tipo_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS espacio_estado_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS vehiculo_tipo_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS usuario_rol_enum"))
