"""Puestos en mantenimiento (punto 4, RN-13): solo el admin, solo sobre un puesto libre, con cupo,
bitacora y traza. Requiere DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from jose import jwt  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ws.connection_manager import connection_manager  # noqa: E402
from tests.test_cupos import API, _cupos, _espacio, _token, admin, client, zona  # noqa: E402,F401
from tests.test_realtime import _esperar_registro, _jwt  # noqa: E402

MOTIVO = "Piso danado"


# Token de admin con un id conocido, para revisar quien queda en la traza.
def _admin_con_id() -> tuple[dict, str]:
    usuario_id = str(uuid.uuid4())
    payload = {"sub": usuario_id, "rol": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return {"Authorization": f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')}"}, usuario_id


def _mantenimiento(client, headers, espacio_id, motivo=MOTIVO):
    return client.post(f"{API}/espacios/{espacio_id}/mantenimiento", headers=headers, json={"motivo": motivo})


def _habilitar(client, headers, espacio_id):
    return client.post(f"{API}/espacios/{espacio_id}/habilitar", headers=headers)


# Trazas de un puesto en auditoria_parqueadero, de la mas vieja a la mas nueva.
def _trazas(espacio_id):
    with SessionLocal() as sesion:
        filas = sesion.execute(
            text(
                "SELECT tabla_afectada, accion::text AS accion, valores_anteriores, valores_nuevos, "
                "realizado_por_id::text AS realizado_por_id, motivo, ip_origen "
                "FROM auditoria_parqueadero WHERE registro_id = :id ORDER BY fecha_hora, id"
            ),
            {"id": espacio_id},
        ).mappings().all()
    return [dict(fila) for fila in filas]


def _ocupacion(client, admin, zona_id):
    return next(z for z in client.get(f"{API}/reportes/ocupacion", headers=admin).json() if z["zona_id"] == zona_id)


def test_mantenimiento_y_habilitar_mueven_el_cupo_y_dejan_dos_trazas(client, zona):
    quien_pone, id_pone = _admin_con_id()
    quien_habilita, id_habilita = _admin_con_id()
    espacio = _espacio(client, quien_pone, zona["id"], codigo="B-12")

    r = _mantenimiento(client, quien_pone, espacio["id"], motivo="  Piso danado  ")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "mantenimiento"
    assert _cupos(client, quien_pone, zona["id"]) == 1
    activo = client.get(f"{API}/espacios/mantenimientos", headers=quien_pone, params={"zona_id": zona["id"]}).json()
    assert [(m["codigo"], m["motivo"], m["iniciado_por_id"]) for m in activo] == [("B-12", MOTIVO, id_pone)]

    r = _habilitar(client, quien_habilita, espacio["id"])
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "libre"
    assert _cupos(client, quien_pone, zona["id"]) == 2
    capacidad = next(z for z in client.get(f"{API}/zonas", headers=quien_pone).json() if z["id"] == zona["id"])
    assert capacidad["capacidad_total"] == 2
    assert client.get(f"{API}/espacios/mantenimientos", headers=quien_pone, params={"zona_id": zona["id"]}).json() == []

    inicio_traza, fin_traza = _trazas(espacio["id"])
    for traza in (inicio_traza, fin_traza):
        assert (traza["tabla_afectada"], traza["accion"], traza["motivo"], traza["ip_origen"]) == (
            "espacios",
            "actualizacion",
            MOTIVO,
            None,
        )

    assert inicio_traza["realizado_por_id"] == id_pone
    assert inicio_traza["valores_anteriores"] == {"estado": "libre"}
    inicio = inicio_traza["valores_nuevos"].pop("inicio")
    assert datetime.fromisoformat(inicio) == datetime.fromisoformat(activo[0]["inicio"])
    assert inicio_traza["valores_nuevos"] == {
        "estado": "mantenimiento",
        "codigo": "B-12",
        "zona_id": zona["id"],
        "zona": zona["nombre"],
        "motivo": MOTIVO,
        "iniciado_por_id": id_pone,
    }

    assert fin_traza["realizado_por_id"] == id_habilita
    assert fin_traza["valores_anteriores"] == {
        "estado": "mantenimiento",
        "motivo": MOTIVO,
        "inicio": inicio,
        "iniciado_por_id": id_pone,
    }
    fin = fin_traza["valores_nuevos"].pop("fin")
    assert datetime.fromisoformat(fin) >= datetime.fromisoformat(inicio)
    assert fin_traza["valores_nuevos"] == {
        "estado": "libre",
        "codigo": "B-12",
        "zona_id": zona["id"],
        "zona": zona["nombre"],
        "habilitado_por_id": id_habilita,
    }


def test_puesto_ocupado_no_va_a_mantenimiento(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="B-13")
    ocupar = {"zona_id": zona["id"], "espacio_id": espacio["id"]}
    assert client.post("/interno/cupos/ocupar", json=ocupar).status_code == 200

    r = _mantenimiento(client, admin, espacio["id"])
    assert r.status_code == 409
    assert "B-13" in r.json()["detail"] and "ocupado" in r.json()["detail"]
    assert _cupos(client, admin, zona["id"]) == 1
    assert _trazas(espacio["id"]) == []


def test_mantenimiento_repetido_y_habilitar_un_libre_dan_409(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="B-14")

    r = _habilitar(client, admin, espacio["id"])
    assert r.status_code == 409
    assert r.json()["detail"] == "El puesto B-14 no esta en mantenimiento"

    assert _mantenimiento(client, admin, espacio["id"]).status_code == 200
    r = _mantenimiento(client, admin, espacio["id"])
    assert r.status_code == 409
    assert r.json()["detail"] == "El puesto B-14 ya esta en mantenimiento"
    assert _cupos(client, admin, zona["id"]) == 1
    assert len(_trazas(espacio["id"])) == 1


def test_puesto_inexistente_da_404(client, admin):
    otro = str(uuid.uuid4())
    assert _mantenimiento(client, admin, otro).status_code == 404
    assert _habilitar(client, admin, otro).status_code == 404


@pytest.mark.parametrize("motivo", ["ab", "   ab   ", "x" * 201])
def test_motivo_corto_o_largo_da_422(client, admin, zona, motivo):
    espacio = _espacio(client, admin, zona["id"], codigo="B-15")
    assert _mantenimiento(client, admin, espacio["id"], motivo=motivo).status_code == 422
    assert client.post(f"{API}/espacios/{espacio['id']}/mantenimiento", headers=admin, json={}).status_code == 422
    assert _cupos(client, admin, zona["id"]) == 2


@pytest.mark.parametrize("rol", ["vigilante", "estudiante"])
def test_solo_el_admin(client, admin, zona, rol):
    espacio = _espacio(client, admin, zona["id"], codigo="B-16")
    otro = _token(rol)
    assert _mantenimiento(client, otro, espacio["id"]).status_code == 403
    assert _habilitar(client, otro, espacio["id"]).status_code == 403
    assert client.get(f"{API}/espacios/mantenimientos", headers=otro).status_code == 403
    assert client.post(f"{API}/espacios/{espacio['id']}/mantenimiento", json={"motivo": MOTIVO}).status_code == 401
    assert client.get(f"{API}/espacios/mantenimientos").status_code == 401
    assert _cupos(client, admin, zona["id"]) == 2


def test_entrar_a_un_puesto_en_mantenimiento_da_409_sin_tocar_el_cupo(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="B-17")
    assert _mantenimiento(client, admin, espacio["id"]).status_code == 200

    r = client.post("/interno/cupos/ocupar", json={"zona_id": zona["id"], "espacio_id": espacio["id"]})
    assert r.status_code == 409
    assert _cupos(client, admin, zona["id"]) == 1


def test_zona_sin_cupo_para_descontar_da_409(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="B-18")
    for _ in range(2):
        assert client.post("/interno/cupos/ocupar", json={"zona_id": zona["id"]}).status_code == 200

    r = _mantenimiento(client, admin, espacio["id"])
    assert r.status_code == 409
    assert zona["nombre"] in r.json()["detail"]
    assert _cupos(client, admin, zona["id"]) == 0
    puesto = next(e for e in client.get(f"{API}/espacios", headers=admin, params={"zona_id": zona["id"]}).json())
    assert puesto["estado"] == "libre"
    assert _trazas(espacio["id"]) == []


def test_la_lista_solo_trae_lo_que_sigue_en_mantenimiento(client, admin, zona):
    uno = _espacio(client, admin, zona["id"], codigo="C-01")
    dos = _espacio(client, admin, zona["id"], codigo="C-02")
    assert _mantenimiento(client, admin, uno["id"]).status_code == 200
    assert _mantenimiento(client, admin, dos["id"], motivo="Pintura").status_code == 200
    assert _habilitar(client, admin, uno["id"]).status_code == 200

    lista = client.get(f"{API}/espacios/mantenimientos", headers=admin, params={"zona_id": zona["id"]}).json()
    assert [(m["espacio_id"], m["codigo"], m["zona_id"], m["motivo"]) for m in lista] == [
        (dos["id"], "C-02", zona["id"], "Pintura")
    ]
    otra_zona = str(uuid.uuid4())
    assert client.get(f"{API}/espacios/mantenimientos", headers=admin, params={"zona_id": otra_zona}).json() == []
    assert dos["id"] in {m["espacio_id"] for m in client.get(f"{API}/espacios/mantenimientos", headers=admin).json()}


def test_el_reporte_no_cuenta_el_mantenimiento_como_ocupado(client, admin, zona):
    uno = _espacio(client, admin, zona["id"], codigo="D-01")
    dos = _espacio(client, admin, zona["id"], codigo="D-02")
    assert _mantenimiento(client, admin, uno["id"]).status_code == 200

    reporte = _ocupacion(client, admin, zona["id"])
    assert (reporte["en_mantenimiento"], reporte["cupos_disponibles"], reporte["porcentaje_ocupacion"]) == (1, 1, 0.0)

    ocupar = {"zona_id": zona["id"], "espacio_id": dos["id"]}
    assert client.post("/interno/cupos/ocupar", json=ocupar).status_code == 200
    assert _ocupacion(client, admin, zona["id"])["porcentaje_ocupacion"] == 100.0


def test_reporte_con_todo_en_mantenimiento_no_divide_por_cero(client, admin):
    nueva = {"nombre": f"Zona {uuid.uuid4().hex[:8]}", "capacidad_total": 1}
    r = client.post(f"{API}/zonas", headers=admin, json=nueva)
    zona_chica = r.json()
    espacio = _espacio(client, admin, zona_chica["id"], codigo="E-01")
    assert _mantenimiento(client, admin, espacio["id"]).status_code == 200

    reporte = _ocupacion(client, admin, zona_chica["id"])
    assert (reporte["en_mantenimiento"], reporte["porcentaje_ocupacion"]) == (1, 0.0)


def test_mantenimiento_y_habilitar_avisan_por_websocket(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="F-01")
    base = len(connection_manager._conexiones)
    with client.websocket_connect("/ws/zonas") as ws:
        ws.send_json({"token": _jwt("estudiante")})
        _esperar_registro(base + 1)

        assert _mantenimiento(client, admin, espacio["id"]).status_code == 200
        assert ws.receive_json() == {"evento": "zona_actualizada", "zona_id": zona["id"], "cupos_disponibles": 1}
        assert _habilitar(client, admin, espacio["id"]).status_code == 200
        assert ws.receive_json() == {"evento": "zona_actualizada", "zona_id": zona["id"], "cupos_disponibles": 2}
    _esperar_registro(base)
