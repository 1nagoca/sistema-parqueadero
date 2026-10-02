"""Autorregistro de estudiantes: estado de verificacion en usuarios y vehiculos, universidad,
consentimiento de datos y tabla de documentos de soporte (carnet, foto de placa, tarjeta de
propiedad).

Los usuarios y vehiculos que ya existen quedan 'aprobado' (los creo un administrador).

Revision ID: 0002_verificacion_estudiantes
Revises: 0001_estructura_inicial
Create Date: 2026-10-02

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002_verificacion_estudiantes"
down_revision: Union[str, None] = "0001_estructura_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE TYPE verificacion_estado_enum AS ENUM ('pendiente', 'aprobado', 'rechazado')"))
    op.execute(sa.text("CREATE TYPE documento_tipo_enum AS ENUM ('carnet', 'foto_placa', 'tarjeta_propiedad')"))

    op.execute(sa.text("ALTER TABLE usuarios ADD COLUMN universidad VARCHAR(150)"))
    op.execute(
        sa.text(
            "ALTER TABLE usuarios ADD COLUMN estado_verificacion verificacion_estado_enum "
            "NOT NULL DEFAULT 'aprobado'"
        )
    )
    op.execute(sa.text("ALTER TABLE usuarios ADD COLUMN motivo_rechazo TEXT"))
    op.execute(sa.text("ALTER TABLE usuarios ADD COLUMN consentimiento_datos_en TIMESTAMPTZ"))

    op.execute(
        sa.text(
            "ALTER TABLE vehiculos ADD COLUMN estado_verificacion verificacion_estado_enum "
            "NOT NULL DEFAULT 'aprobado'"
        )
    )
    op.execute(sa.text("ALTER TABLE vehiculos ADD COLUMN motivo_rechazo TEXT"))

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


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS documentos"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP COLUMN IF EXISTS motivo_rechazo"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP COLUMN IF EXISTS estado_verificacion"))
    op.execute(sa.text("ALTER TABLE usuarios DROP COLUMN IF EXISTS consentimiento_datos_en"))
    op.execute(sa.text("ALTER TABLE usuarios DROP COLUMN IF EXISTS motivo_rechazo"))
    op.execute(sa.text("ALTER TABLE usuarios DROP COLUMN IF EXISTS estado_verificacion"))
    op.execute(sa.text("ALTER TABLE usuarios DROP COLUMN IF EXISTS universidad"))
    op.execute(sa.text("DROP TYPE IF EXISTS documento_tipo_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS verificacion_estado_enum"))
