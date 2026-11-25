"""Mantenimiento de puestos: bitacora mantenimientos (lo que esta en mantenimiento ahora) y
auditoria_parqueadero (solo se agregan filas), con el enum de acciones de auditoria.

Revision ID: 0003_mantenimiento
Revises: 0002_quitar_reservado
Create Date: 2026-11-25

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Identificadores de Alembic: va despues de quitar reservado.
revision: str = "0003_mantenimiento"
down_revision: Union[str, None] = "0002_quitar_reservado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Aplica la migracion (alembic upgrade head).
def upgrade() -> None:
    # Acciones de auditoria: los mismos valores que en accesos e identidad.
    op.execute(sa.text("CREATE TYPE auditoria_accion_enum AS ENUM ('creacion', 'actualizacion', 'eliminacion')"))

    # Bitacora: un puesto aparece aqui solo mientras esta en mantenimiento.
    op.execute(
        sa.text(
            """
            CREATE TABLE mantenimientos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                espacio_id UUID NOT NULL,
                motivo VARCHAR(200) NOT NULL,
                iniciado_por_id UUID NOT NULL,
                inicio TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_mantenimientos_espacio_id UNIQUE (espacio_id),
                CONSTRAINT fk_mantenimientos_espacio_id
                    FOREIGN KEY (espacio_id) REFERENCES espacios(id) ON DELETE RESTRICT,
                CONSTRAINT ck_mantenimientos_motivo_largo CHECK (char_length(motivo) BETWEEN 3 AND 200)
            )
            """
        )
    )

    # Auditoria del servicio: mismas columnas que auditoria_accesos; realizado_por_id es un usuario de identidad, sin FK.
    op.execute(
        sa.text(
            """
            CREATE TABLE auditoria_parqueadero (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tabla_afectada VARCHAR(50) NOT NULL,
                registro_id UUID NOT NULL,
                accion auditoria_accion_enum NOT NULL,
                valores_anteriores JSONB,
                valores_nuevos JSONB,
                realizado_por_id UUID NOT NULL,
                motivo TEXT,
                fecha_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
                ip_origen VARCHAR(45)
            )
            """
        )
    )
    # Indices para buscar la historia de un puesto y por fecha.
    op.execute(
        sa.text(
            "CREATE INDEX idx_auditoria_parqueadero_registro ON auditoria_parqueadero (tabla_afectada, registro_id)"
        )
    )
    op.execute(sa.text("CREATE INDEX idx_auditoria_parqueadero_fecha_hora ON auditoria_parqueadero (fecha_hora)"))


# Deshace la migracion: aborta si hay puestos en mantenimiento o trazas (la auditoria no se borra).
def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                en_mantenimiento INTEGER;
                trazas INTEGER;
            BEGIN
                SELECT count(*) INTO en_mantenimiento FROM mantenimientos;
                IF en_mantenimiento > 0 THEN
                    RAISE EXCEPTION 'No se puede deshacer el mantenimiento: hay % puesto(s) en mantenimiento. Habilitelos y vuelva a intentarlo.', en_mantenimiento;
                END IF;
                SELECT count(*) INTO trazas FROM auditoria_parqueadero;
                IF trazas > 0 THEN
                    RAISE EXCEPTION 'No se puede deshacer el mantenimiento: auditoria_parqueadero tiene % traza(s) y la auditoria no se borra.', trazas;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(sa.text("DROP TABLE IF EXISTS auditoria_parqueadero"))
    op.execute(sa.text("DROP TABLE IF EXISTS mantenimientos"))
    op.execute(sa.text("DROP TYPE IF EXISTS auditoria_accion_enum"))
