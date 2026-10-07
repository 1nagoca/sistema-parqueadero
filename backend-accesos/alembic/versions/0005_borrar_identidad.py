"""Las tablas de identidad (usuarios, vehiculos y documentos) viven ahora en el servicio de
identidad (backend-identidad), con su propia base de datos. Aqui se eliminan junto con los
enums que solo ellas usaban; accesos y auditoria_accesos ya no dependen de ellas (0004).

No se copian datos: la base de identidad se siembra aparte (ver docs/arquitectura.md). Para no
perder datos por descuido, la migracion se niega a correr si alguna de esas tablas tiene
filas, salvo que se confirme con la variable de entorno IDENTIDAD_DATOS_MIGRADOS=1.

Revision ID: 0005_borrar_identidad
Revises: 0004_placa_en_accesos
Create Date: 2026-10-06

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005_borrar_identidad"
down_revision: Union[str, None] = "0004_placa_en_accesos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    hay_datos = op.get_bind().execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM documentos) OR EXISTS (SELECT 1 FROM vehiculos) "
            "OR EXISTS (SELECT 1 FROM usuarios)"
        )
    ).scalar()
    if hay_datos and os.environ.get("IDENTIDAD_DATOS_MIGRADOS") != "1":
        raise RuntimeError(
            "Las tablas usuarios, vehiculos o documentos tienen datos. Si ya no hacen falta "
            "(identidad vive en su propio servicio), vuelve a correr con "
            "IDENTIDAD_DATOS_MIGRADOS=1 (ver docs/arquitectura.md)."
        )

    op.execute(sa.text("DROP TABLE documentos"))
    op.execute(sa.text("DROP TABLE vehiculos"))
    op.execute(sa.text("DROP TABLE usuarios"))

    op.execute(sa.text("DROP TYPE documento_tipo_enum"))
    op.execute(sa.text("DROP TYPE vehiculo_tipo_enum"))
    op.execute(sa.text("DROP TYPE verificacion_estado_enum"))
    op.execute(sa.text("DROP TYPE usuario_rol_enum"))


def downgrade() -> None:
    """Restaura la estructura, sin datos: los usuarios, vehiculos y documentos estan en la base
    del servicio de identidad."""
    op.execute(sa.text("CREATE TYPE usuario_rol_enum AS ENUM ('estudiante', 'docente', 'administrativo', 'vigilante', 'admin')"))
    op.execute(sa.text("CREATE TYPE verificacion_estado_enum AS ENUM ('pendiente', 'aprobado', 'rechazado')"))
    op.execute(sa.text("CREATE TYPE vehiculo_tipo_enum AS ENUM ('carro', 'moto', 'bicicleta', 'otro')"))
    op.execute(sa.text("CREATE TYPE documento_tipo_enum AS ENUM ('carnet', 'foto_placa', 'tarjeta_propiedad')"))

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
                actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                universidad VARCHAR(150),
                estado_verificacion verificacion_estado_enum NOT NULL DEFAULT 'aprobado',
                motivo_rechazo TEXT,
                consentimiento_datos_en TIMESTAMPTZ
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
                estado_verificacion verificacion_estado_enum NOT NULL DEFAULT 'aprobado',
                motivo_rechazo TEXT,
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
