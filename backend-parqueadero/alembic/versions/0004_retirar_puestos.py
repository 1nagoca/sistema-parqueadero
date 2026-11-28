"""Pasa el plano a 800 puestos (punto 5): retira 200 puestos, los de numero mas alto de cada
bloque (A-H del 34 al 42, I-V del 38 al 46, W-10 y X-10), sin borrarlos: quedan en el estado
nuevo 'retirado' para que el historial y la bitacora de mantenimientos conserven su puesto. Cada
zona baja su capacidad y sus cupos en lo que retira.

Revision ID: 0004_retirar_puestos
Revises: 0003_mantenimiento
Create Date: 2026-11-27

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# Identificadores de Alembic: va despues del mantenimiento.
revision: str = "0004_retirar_puestos"
down_revision: Union[str, None] = "0003_mantenimiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Los 200 codigos que salen, como CTE: A-H del 34 al 42, I-V del 38 al 46, W-10 y X-10.
RETIRADOS = """
    retirados(codigo) AS (
        SELECT letra || '-' || lpad(numero::text, 2, '0')
        FROM unnest(ARRAY['A','B','C','D','E','F','G','H']) AS letra, generate_series(34, 42) AS numero
        UNION ALL
        SELECT letra || '-' || lpad(numero::text, 2, '0')
        FROM unnest(ARRAY['I','J','K','L','M','N','O','P','Q','R','S','T','U','V']) AS letra,
             generate_series(38, 46) AS numero
        UNION ALL
        SELECT letra || '-10' FROM unnest(ARRAY['W','X']) AS letra
    )
"""


# Cambia la columna estado al tipo con esos valores y le devuelve su default (como la 0002).
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


# Aplica la migracion: se detiene sin cambiar nada si algun puesto o zona no lo permite.
def upgrade() -> None:
    # Ninguno de los 200 puede estar ocupado o en mantenimiento.
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                bloqueados TEXT;
            BEGIN
                WITH {RETIRADOS}
                SELECT string_agg(z.nombre || ': ' || e.codigo || ' (' || e.estado::text || ')', ', '
                                  ORDER BY z.nombre, e.codigo)
                INTO bloqueados
                FROM espacios e JOIN zonas z ON z.id = e.zona_id
                WHERE e.codigo IN (SELECT codigo FROM retirados) AND e.estado <> 'libre';
                IF bloqueados IS NOT NULL THEN
                    RAISE EXCEPTION 'No se pueden retirar puestos ocupados o en mantenimiento: %. Liberelos o habilitelos y vuelva a migrar.', bloqueados;
                END IF;
            END
            $$
            """
        )
    )
    # Ninguna zona puede quedar sin capacidad ni con cupos fuera de rango.
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                invalidas TEXT;
            BEGIN
                WITH {RETIRADOS},
                por_zona AS (
                    SELECT zona_id, count(*) AS n FROM espacios
                    WHERE codigo IN (SELECT codigo FROM retirados) GROUP BY zona_id
                )
                SELECT string_agg(z.nombre || ' (capacidad ' || (z.capacidad_total - p.n)::text
                                  || ', cupos ' || (z.cupos_disponibles - p.n)::text || ')', ', ')
                INTO invalidas
                FROM zonas z JOIN por_zona p ON p.zona_id = z.id
                WHERE z.capacidad_total - p.n <= 0 OR z.cupos_disponibles - p.n < 0;
                IF invalidas IS NOT NULL THEN
                    RAISE EXCEPTION 'Retirar los puestos dejaria zonas fuera de rango: %. Revise sus cupos y vuelva a migrar.', invalidas;
                END IF;
            END
            $$
            """
        )
    )

    # Tipo nuevo con 'retirado' (ADD VALUE no se puede usar en la misma transaccion).
    _cambiar_tipo("'libre', 'ocupado', 'mantenimiento', 'retirado'")

    # Cada zona baja capacidad y cupos en lo que retira; despues sus puestos pasan a retirado.
    op.execute(
        sa.text(
            f"""
            WITH {RETIRADOS},
            por_zona AS (
                SELECT zona_id, count(*) AS n FROM espacios
                WHERE codigo IN (SELECT codigo FROM retirados) GROUP BY zona_id
            )
            UPDATE zonas z
            SET capacidad_total = z.capacidad_total - p.n,
                cupos_disponibles = z.cupos_disponibles - p.n,
                actualizado_en = now()
            FROM por_zona p WHERE p.zona_id = z.id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH {RETIRADOS}
            UPDATE espacios SET estado = 'retirado', actualizado_en = now()
            WHERE codigo IN (SELECT codigo FROM retirados)
            """
        )
    )


# Deshace la migracion: los retirados vuelven a libre y cada zona recupera lo que retiro.
def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE zonas z
            SET capacidad_total = z.capacidad_total + p.n,
                cupos_disponibles = z.cupos_disponibles + p.n,
                actualizado_en = now()
            FROM (SELECT zona_id, count(*) AS n FROM espacios WHERE estado = 'retirado' GROUP BY zona_id) p
            WHERE p.zona_id = z.id
            """
        )
    )
    op.execute(sa.text("UPDATE espacios SET estado = 'libre', actualizado_en = now() WHERE estado = 'retirado'"))
    _cambiar_tipo("'libre', 'ocupado', 'mantenimiento'")
