"""Cierre de semestre (RN-10): archiva y borra los accesos cerrados antes del semestre anterior y
sus trazas. Solo como comando, nunca por HTTP:

    docker compose exec backend-accesos python -m app.db.cierre_semestre --admin-id <uuid> [--confirmar]

Sin --confirmar es un simulacro: muestra el corte y cuanto saldria, sin tocar nada.
"""

import argparse
import sys
import uuid
from pathlib import Path

from app.db.session import SessionLocal
from app.services import cierre_semestre_service


# Lee los argumentos, corre el cierre y muestra el resultado; devuelve el codigo de salida.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.db.cierre_semestre",
        description="Archiva y borra los accesos cerrados antes del semestre anterior (RN-10).",
    )
    parser.add_argument("--admin-id", required=True, type=uuid.UUID, help="id de un administrador activo")
    parser.add_argument("--confirmar", action="store_true", help="archiva y borra; sin esto es un simulacro")
    parser.add_argument("--carpeta", type=Path, default=Path("/archivo"), help="donde guardar el archivo")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        try:
            resultado = cierre_semestre_service.cerrar_semestre(
                db, admin_id=args.admin_id, carpeta=args.carpeta, confirmar=args.confirmar
            )
        except cierre_semestre_service.CierreError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    for linea in cierre_semestre_service.resumen(resultado):
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
