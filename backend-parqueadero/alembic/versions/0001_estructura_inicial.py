"""Estructura inicial del servicio de parqueadero: zonas y espacios, con las restricciones
que aplican RN-01 (descuento de cupo) y RN-02 (liberacion de cupo).

Revision ID: 0001_estructura_inicial
Revises:
Create Date: 2026-10-04

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_estructura_inicial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE TYPE espacio_estado_enum AS ENUM ('libre', 'ocupado', 'reservado', 'mantenimiento')"))

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


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS espacios"))
    op.execute(sa.text("DROP TABLE IF EXISTS zonas"))
    op.execute(sa.text("DROP TYPE IF EXISTS espacio_estado_enum"))
