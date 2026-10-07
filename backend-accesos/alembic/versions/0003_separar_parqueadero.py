"""Zonas y espacios pasan al microservicio de parqueadero (backend-parqueadero), que tiene su
propia base de datos. Aqui se eliminan las tablas y las llaves foraneas que apuntaban a ellas:
accesos conserva zona_id y espacio_id como identificadores sin restriccion.

Antes de aplicar esta migracion en una base con datos hay que copiar zonas y espacios a la
base del servicio de parqueadero (ver docs/arquitectura.md). Para no perderlos por descuido,
la migracion se niega a correr si aun hay zonas, salvo que se confirme con la variable de
entorno PARQUEADERO_DATOS_MIGRADOS=1.

Revision ID: 0003_separar_parqueadero
Revises: 0002_verificacion_estudiantes
Create Date: 2026-10-04

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_separar_parqueadero"
down_revision: Union[str, None] = "0002_verificacion_estudiantes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    hay_zonas = op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM zonas)")).scalar()
    if hay_zonas and os.environ.get("PARQUEADERO_DATOS_MIGRADOS") != "1":
        raise RuntimeError(
            "La tabla zonas tiene datos. Copialos primero a la base del servicio de parqueadero "
            "y vuelve a correr con PARQUEADERO_DATOS_MIGRADOS=1 (ver docs/arquitectura.md)."
        )

    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT accesos_zona_id_fkey"))
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT accesos_espacio_id_fkey"))
    op.execute(sa.text("DROP TABLE espacios"))
    op.execute(sa.text("DROP TABLE zonas"))
    op.execute(sa.text("DROP TYPE espacio_estado_enum"))


def downgrade() -> None:
    """Restaura la estructura; los datos de zonas y espacios hay que traerlos de vuelta desde
    la base del servicio de parqueadero. Las llaves foraneas se crean NOT VALID para que los
    accesos existentes no bloqueen el downgrade mientras tanto."""
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
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT accesos_zona_id_fkey "
            "FOREIGN KEY (zona_id) REFERENCES zonas(id) ON DELETE RESTRICT NOT VALID"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT accesos_espacio_id_fkey "
            "FOREIGN KEY (espacio_id) REFERENCES espacios(id) ON DELETE RESTRICT NOT VALID"
        )
    )
