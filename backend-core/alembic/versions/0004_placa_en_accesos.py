"""Accesos deja de depender de las tablas de identidad: guarda la placa del vehiculo y pierde
las llaves foraneas hacia usuarios y vehiculos (y la de auditoria_accesos.realizado_por_id).
vehiculo_id, usuario_id, autorizado_por_id y realizado_por_id quedan como identificadores sin
restriccion, igual que zona_id y espacio_id.

Revision ID: 0004_placa_en_accesos
Revises: 0003_separar_parqueadero
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004_placa_en_accesos"
down_revision: Union[str, None] = "0003_separar_parqueadero"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE accesos ADD COLUMN placa VARCHAR(10)"))
    op.execute(
        sa.text("UPDATE accesos SET placa = vehiculos.placa FROM vehiculos WHERE vehiculos.id = accesos.vehiculo_id")
    )
    sin_placa = op.get_bind().execute(sa.text("SELECT count(*) FROM accesos WHERE placa IS NULL")).scalar()
    if sin_placa:
        raise RuntimeError(
            f"{sin_placa} accesos apuntan a un vehiculo que no esta en la tabla vehiculos: no se "
            "puede saber su placa. Corrigelos antes de volver a correr la migracion."
        )
    op.execute(sa.text("ALTER TABLE accesos ALTER COLUMN placa SET NOT NULL"))
    op.execute(
        sa.text("ALTER TABLE accesos ADD CONSTRAINT ck_accesos_placa_mayusculas CHECK (placa = upper(placa))")
    )

    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT accesos_vehiculo_id_fkey"))
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT accesos_usuario_id_fkey"))
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT accesos_autorizado_por_id_fkey"))
    op.execute(sa.text("ALTER TABLE auditoria_accesos DROP CONSTRAINT auditoria_accesos_realizado_por_id_fkey"))


def downgrade() -> None:
    """Las llaves foraneas se crean NOT VALID para que los accesos y trazas registrados sin
    ellas no bloqueen el downgrade. La placa guardada se pierde."""
    op.execute(
        sa.text(
            "ALTER TABLE auditoria_accesos ADD CONSTRAINT auditoria_accesos_realizado_por_id_fkey "
            "FOREIGN KEY (realizado_por_id) REFERENCES usuarios(id) ON DELETE RESTRICT NOT VALID"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT accesos_autorizado_por_id_fkey "
            "FOREIGN KEY (autorizado_por_id) REFERENCES usuarios(id) ON DELETE RESTRICT NOT VALID"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT accesos_usuario_id_fkey "
            "FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE RESTRICT NOT VALID"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE accesos ADD CONSTRAINT accesos_vehiculo_id_fkey "
            "FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id) ON DELETE RESTRICT NOT VALID"
        )
    )
    op.execute(sa.text("ALTER TABLE accesos DROP CONSTRAINT ck_accesos_placa_mayusculas"))
    op.execute(sa.text("ALTER TABLE accesos DROP COLUMN placa"))
