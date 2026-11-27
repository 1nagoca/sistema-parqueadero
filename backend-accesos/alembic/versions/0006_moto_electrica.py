"""Moto electrica en accesos: el acceso de una electrica no lleva placa sino el numero de serie
copiado de identidad, y solo puede ser normal (la electrica es de un estudiante). Los accesos de
hoy quedan como de motos con placa sin tocar sus datos.

Revision ID: 0006_moto_electrica
Revises: 0005_borrar_identidad
Create Date: 2026-11-27

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Identificadores de Alembic: esta es la 0006 y va despues de la 0005.
revision: str = "0006_moto_electrica"
down_revision: Union[str, None] = "0005_borrar_identidad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Aplica la migracion: los accesos de hoy quedan con es_electrica = false.
def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE accesos ADD COLUMN es_electrica BOOLEAN NOT NULL DEFAULT false"))
    op.execute(sa.text("ALTER TABLE accesos ADD COLUMN numero_serie VARCHAR(17)"))
    op.execute(sa.text("ALTER TABLE accesos ALTER COLUMN placa DROP NOT NULL"))

    # Igual que en identidad: con placa y sin serial, o electrica con serial y sin placa.
    op.execute(
        sa.text(
            """
            ALTER TABLE accesos ADD CONSTRAINT ck_accesos_placa_o_numero_serie CHECK (
                (es_electrica = false AND placa IS NOT NULL AND numero_serie IS NULL)
                OR (es_electrica = true AND placa IS NULL AND numero_serie IS NOT NULL)
            )
            """
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT ck_accesos_numero_serie_mayusculas "
            "CHECK (numero_serie = upper(numero_serie))"
        )
    )
    # La electrica es de un estudiante: nunca entra como visitante.
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT ck_accesos_electrica_solo_normal "
            "CHECK (es_electrica = false OR tipo_acceso = 'normal')"
        )
    )


# Deshace la migracion: aborta si hay accesos de electricas, nunca les inventa una placa.
def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                electricas INTEGER;
            BEGIN
                SELECT count(*) INTO electricas FROM accesos WHERE es_electrica;
                IF electricas > 0 THEN
                    RAISE EXCEPTION 'No se puede quitar la moto electrica de accesos: hay % acceso(s) de motos electricas. Archivelos o retirelos y vuelva a migrar.', electricas;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT ck_accesos_electrica_solo_normal"))
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT ck_accesos_numero_serie_mayusculas"))
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT ck_accesos_placa_o_numero_serie"))
    op.execute(sa.text("ALTER TABLE accesos DROP COLUMN numero_serie"))
    op.execute(sa.text("ALTER TABLE accesos DROP COLUMN es_electrica"))
    op.execute(sa.text("ALTER TABLE accesos ALTER COLUMN placa SET NOT NULL"))
