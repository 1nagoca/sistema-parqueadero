"""Quita el estado 'reservado' de los espacios: ninguna ruta lo asigna y solo queda
mantenimiento. Postgres no borra valores de un ENUM, asi que se recrea el tipo.

Revision ID: 0002_quitar_reservado
Revises: 0001_estructura_inicial
Create Date: 2026-11-25

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Identificadores de Alembic: va despues de la estructura inicial.
revision: str = "0002_quitar_reservado"
down_revision: Union[str, None] = "0001_estructura_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Cambia la columna estado al tipo indicado y le devuelve su default.
def _cambiar_tipo(valores: str) -> None:
    op.execute(sa.text("ALTER TYPE espacio_estado_enum RENAME TO espacio_estado_enum_viejo"))
    op.execute(sa.text(f"CREATE TYPE espacio_estado_enum AS ENUM ({valores})"))
    op.execute(sa.text("ALTER TABLE espacios ALTER COLUMN estado DROP DEFAULT"))
    op.execute(
        sa.text(
            "ALTER TABLE espacios ALTER COLUMN estado TYPE espacio_estado_enum "
            "USING estado::text::espacio_estado_enum"
        )
    )
    op.execute(sa.text("ALTER TABLE espacios ALTER COLUMN estado SET DEFAULT 'libre'"))
    op.execute(sa.text("DROP TYPE espacio_estado_enum_viejo"))


# Aplica la migracion: aborta si queda algun puesto reservado, nunca lo convierte.
def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                reservados INTEGER;
            BEGIN
                SELECT count(*) INTO reservados FROM espacios WHERE estado = 'reservado';
                IF reservados > 0 THEN
                    RAISE EXCEPTION 'No se puede quitar el estado reservado: hay % puesto(s) en reservado. Paselos a libre o mantenimiento y vuelva a migrar.', reservados;
                END IF;
            END
            $$
            """
        )
    )
    _cambiar_tipo("'libre', 'ocupado', 'mantenimiento'")


# Deshace la migracion: vuelve a poner 'reservado' en el mismo orden que la 0001.
def downgrade() -> None:
    _cambiar_tipo("'libre', 'ocupado', 'reservado', 'mantenimiento'")
