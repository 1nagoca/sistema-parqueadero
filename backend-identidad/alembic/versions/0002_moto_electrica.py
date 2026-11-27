"""Moto electrica: sin placa, con numero de serie unico y solo de estudiantes; foto del serial
como documento nuevo. Las motos de hoy quedan como normales sin tocar sus datos.

Revision ID: 0002_moto_electrica
Revises: 0001_estructura_inicial
Create Date: 2026-11-27

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Identificadores de Alembic: va despues de la estructura inicial.
revision: str = "0002_moto_electrica"
down_revision: Union[str, None] = "0001_estructura_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# CHECK de documentos de la 0001; compara con el enum, asi que se quita y repone al recrear el tipo.
CK_DOCUMENTOS = "(tipo = 'carnet' AND vehiculo_id IS NULL) OR (tipo <> 'carnet' AND vehiculo_id IS NOT NULL)"


# Aplica la migracion (alembic upgrade head).
def upgrade() -> None:
    # Foto del serial del chasis o de la lamina tecnica.
    op.execute(sa.text("ALTER TYPE documento_tipo_enum ADD VALUE 'foto_serial'"))

    # Columnas nuevas; las motos de hoy quedan con es_electrica = false.
    op.execute(sa.text("ALTER TABLE vehiculos ADD COLUMN es_electrica BOOLEAN NOT NULL DEFAULT false"))
    op.execute(sa.text("ALTER TABLE vehiculos ADD COLUMN numero_serie VARCHAR(17)"))
    op.execute(sa.text("ALTER TABLE vehiculos ALTER COLUMN placa DROP NOT NULL"))

    # Normal: con placa y sin serial; electrica: con serial y sin placa.
    op.execute(
        sa.text(
            """
            ALTER TABLE vehiculos ADD CONSTRAINT ck_vehiculos_placa_o_numero_serie CHECK (
                (es_electrica = false AND placa IS NOT NULL AND numero_serie IS NULL)
                OR (es_electrica = true AND placa IS NULL AND numero_serie IS NOT NULL)
            )
            """
        )
    )
    # La electrica es solo de estudiantes: con dueno y nunca de visitante.
    op.execute(
        sa.text(
            "ALTER TABLE vehiculos ADD CONSTRAINT ck_vehiculos_electrica_solo_estudiante "
            "CHECK (es_electrica = false OR (usuario_id IS NOT NULL AND es_visitante = false))"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE vehiculos ADD CONSTRAINT ck_vehiculos_numero_serie_mayusculas "
            "CHECK (numero_serie = upper(numero_serie))"
        )
    )
    # Serial unico sin contar guiones: EB2024-00871 y EB202400871 chocan.
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_vehiculos_numero_serie ON vehiculos (replace(numero_serie, '-', '')) "
            "WHERE numero_serie IS NOT NULL"
        )
    )


# Deshace la migracion: aborta si hay electricas o fotos del serial, nunca las convierte.
def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                electricas INTEGER;
                fotos INTEGER;
            BEGIN
                SELECT count(*) INTO electricas FROM vehiculos WHERE es_electrica;
                SELECT count(*) INTO fotos FROM documentos WHERE tipo::text = 'foto_serial';
                IF electricas > 0 OR fotos > 0 THEN
                    RAISE EXCEPTION 'No se puede quitar la moto electrica: hay % moto(s) electrica(s) y % documento(s) foto_serial. Retirelos y vuelva a migrar.', electricas, fotos;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(sa.text("DROP INDEX uq_vehiculos_numero_serie"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP CONSTRAINT ck_vehiculos_numero_serie_mayusculas"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP CONSTRAINT ck_vehiculos_electrica_solo_estudiante"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP CONSTRAINT ck_vehiculos_placa_o_numero_serie"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP COLUMN numero_serie"))
    op.execute(sa.text("ALTER TABLE vehiculos DROP COLUMN es_electrica"))
    op.execute(sa.text("ALTER TABLE vehiculos ALTER COLUMN placa SET NOT NULL"))

    # Postgres no borra valores de un ENUM: se recrea el tipo sin foto_serial.
    op.execute(sa.text("ALTER TYPE documento_tipo_enum RENAME TO documento_tipo_enum_viejo"))
    op.execute(sa.text("CREATE TYPE documento_tipo_enum AS ENUM ('carnet', 'foto_placa', 'tarjeta_propiedad')"))
    op.execute(sa.text("ALTER TABLE documentos DROP CONSTRAINT ck_documentos_vehiculo_segun_tipo"))
    op.execute(
        sa.text(
            "ALTER TABLE documentos ALTER COLUMN tipo TYPE documento_tipo_enum "
            "USING tipo::text::documento_tipo_enum"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE documentos ADD CONSTRAINT ck_documentos_vehiculo_segun_tipo CHECK ({CK_DOCUMENTOS})")
    )
    op.execute(sa.text("DROP TYPE documento_tipo_enum_viejo"))
