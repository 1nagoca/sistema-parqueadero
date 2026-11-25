"""Auditoria del mantenimiento (GET /espacios/auditoria): solo lectura, por periodo y paginada, como las
bitacoras de accesos e identidad. Requiere DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la
prepara conftest."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from tests.test_cupos import API, _espacio, _token, admin, client, zona  # noqa: E402,F401

RUTA = f"{API}/espacios/auditoria"


def _mantenimiento(client, admin, espacio_id):
    r = client.post(f"{API}/espacios/{espacio_id}/mantenimiento", headers=admin, json={"motivo": "Piso danado"})
    assert r.status_code == 200, r.text


def _habilitar(client, admin, espacio_id):
    r = client.post(f"{API}/espacios/{espacio_id}/habilitar", headers=admin)
    assert r.status_code == 200, r.text


def test_por_defecto_trae_el_semestre_actual(client, admin):
    from app.services.auditoria_service import hoy_en_colombia, semestre_de

    r = client.get(RUTA, headers=admin)
    assert r.status_code == 200, r.text
    semestre = semestre_de(hoy_en_colombia())
    cuerpo = r.json()
    assert (cuerpo["desde"], cuerpo["hasta"]) == (semestre.inicio.isoformat(), semestre.fin.isoformat())
    assert (cuerpo["pagina"], cuerpo["por_pagina"]) == (1, 50)


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "2026-08-10", "hasta": "2026-08-01"},
        {"desde": "2026-08-01"},
        {"desde": "2026-01-01", "hasta": "2026-07-04"},
        {"por_pagina": 201},
        {"pagina": 0},
    ],
)
def test_rango_o_pagina_que_no_sirven_dan_422(client, admin, params):
    assert client.get(RUTA, headers=admin, params=params).status_code == 422


def test_un_periodo_pasado_no_trae_nada(client, admin):
    cuerpo = client.get(RUTA, headers=admin, params={"desde": "2020-01-01", "hasta": "2020-01-31"}).json()
    assert (cuerpo["items"], cuerpo["total"]) == ([], 0)


def test_trae_las_dos_trazas_de_un_mantenimiento_de_la_mas_nueva_a_la_mas_vieja(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="G-01")
    _mantenimiento(client, admin, espacio["id"])
    _habilitar(client, admin, espacio["id"])

    items = client.get(RUTA, headers=admin, params={"tabla_afectada": "espacios", "por_pagina": 200}).json()["items"]
    del_puesto = [t for t in items if t["registro_id"] == espacio["id"]]
    assert [t["valores_nuevos"]["estado"] for t in del_puesto] == ["libre", "mantenimiento"]
    habilitar, inicio = del_puesto
    assert (inicio["accion"], inicio["tabla_afectada"]) == ("actualizacion", "espacios")
    assert inicio["motivo"] == "Piso danado"
    assert inicio["valores_nuevos"]["codigo"] == "G-01" and inicio["valores_nuevos"]["zona"] == zona["nombre"]
    assert habilitar["valores_anteriores"]["inicio"] == inicio["valores_nuevos"]["inicio"]
    assert "fin" in habilitar["valores_nuevos"] and "habilitado_por_id" in habilitar["valores_nuevos"]
    assert {"id", "realizado_por_id", "fecha_hora", "ip_origen", "valores_anteriores"} <= set(inicio)


def test_paginacion_total_y_orden(client, admin, zona):
    antes = client.get(RUTA, headers=admin).json()["total"]
    espacio = _espacio(client, admin, zona["id"], codigo="G-02")
    _mantenimiento(client, admin, espacio["id"])
    _habilitar(client, admin, espacio["id"])
    _mantenimiento(client, admin, espacio["id"])

    primera = client.get(RUTA, headers=admin, params={"pagina": 1, "por_pagina": 2}).json()
    segunda = client.get(RUTA, headers=admin, params={"pagina": 2, "por_pagina": 2}).json()
    assert primera["total"] == segunda["total"] == antes + 3
    assert [t["valores_nuevos"]["estado"] for t in primera["items"]] == ["mantenimiento", "libre"]
    assert segunda["items"][0]["valores_nuevos"]["estado"] == "mantenimiento"
    assert segunda["items"][0]["registro_id"] == espacio["id"]
    fechas = [t["fecha_hora"] for t in primera["items"] + segunda["items"]]
    assert fechas == sorted(fechas, reverse=True)
    assert not {t["id"] for t in primera["items"]} & {t["id"] for t in segunda["items"]}


def test_filtro_por_tabla(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"], codigo="G-03")
    _mantenimiento(client, admin, espacio["id"])

    espacios = client.get(RUTA, headers=admin, params={"tabla_afectada": "espacios"}).json()
    assert espacios["total"] >= 1 and all(t["tabla_afectada"] == "espacios" for t in espacios["items"])
    assert client.get(RUTA, headers=admin, params={"tabla_afectada": "accesos"}).json()["total"] == 0


@pytest.mark.parametrize("rol", ["vigilante", "estudiante"])
def test_solo_el_admin(client, rol):
    assert client.get(RUTA, headers=_token(rol)).status_code == 403
    assert client.get(RUTA).status_code == 401


def test_no_hay_rutas_para_escribir_en_la_auditoria(client, admin):
    assert client.post(RUTA, headers=admin, json={}).status_code == 405
    assert client.delete(RUTA, headers=admin).status_code == 405
