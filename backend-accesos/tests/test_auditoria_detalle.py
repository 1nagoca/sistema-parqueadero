"""GET /auditoria agrega a cada traza de accesos un detalle (placa, tipo, zona, codigo del puesto y,
en la salida, la duracion) leido de la tabla accesos con un LEFT JOIN; el codigo del puesto se pide a
parqueadero una sola vez por pagina. Los dobles de parqueadero e identidad vienen de test_accesos."""

import os
import uuid
from types import SimpleNamespace

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.auditoria_acceso import AuditoriaAcceso  # noqa: E402
from app.models.enums import AccionAuditoria  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _entrada_visitante,
    admin,
    client,
    identidad,
    parqueadero,
)

API = settings.API_V1_PREFIX
CAMPOS = {
    "id", "tabla_afectada", "registro_id", "accion", "valores_anteriores", "valores_nuevos",
    "realizado_por_id", "motivo", "fecha_hora", "ip_origen", "detalle",
}


@pytest.fixture
def codigos(monkeypatch, parqueadero):
    """Parqueadero responde el codigo de los puestos que conoce y anota cada llamada."""
    espia = SimpleNamespace(nombres={}, llamadas=[])

    def codigos_de_espacios(espacio_ids):
        espia.llamadas.append(list(espacio_ids))
        return {e: espia.nombres[e] for e in espacio_ids if e in espia.nombres}

    monkeypatch.setattr(parqueadero_client, "codigos_de_espacios", codigos_de_espacios)
    return espia


def _entrada_normal(client, admin, identidad, codigos, codigo="B-12"):
    """Entra una moto aprobada con dueno en un puesto con ese codigo; devuelve el acceso y su placa."""
    moto = identidad.vehiculo("AUD", propietario_estado="aprobado")
    espacio_id = uuid.uuid4()
    codigos.nombres[espacio_id] = codigo
    zona_id = str(uuid.uuid4())
    r = client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={"vehiculo_id": moto["id"], "zona_id": zona_id, "espacio_id": str(espacio_id)},
    )
    assert r.status_code == 201, r.text
    return {"acceso": r.json(), "placa": moto["placa"], "zona_id": zona_id, "espacio_id": espacio_id}


def _trazas_de(client, admin, acceso_id, **params):
    """Las trazas de ese acceso en la primera pagina (las mas nuevas) de la tabla accesos."""
    r = client.get(f"{API}/auditoria", headers=admin, params={"tabla_afectada": "accesos", "por_pagina": 200, **params})
    assert r.status_code == 200, r.text
    return {t["accion"]: t for t in r.json()["items"] if t["registro_id"] == acceso_id}


def test_entrada_y_salida_traen_placa_tipo_zona_puesto_y_la_duracion_solo_en_la_salida(client, admin, identidad, codigos):
    entrada = _entrada_normal(client, admin, identidad, codigos)
    acceso_id = entrada["acceso"]["id"]
    salida = client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin)
    assert salida.status_code == 200, salida.text

    trazas = _trazas_de(client, admin, acceso_id)
    assert set(trazas["creacion"]) == CAMPOS
    assert trazas["creacion"]["detalle"] == {
        "placa": entrada["placa"],
        "tipo_acceso": "normal",
        "zona_id": entrada["zona_id"],
        "espacio_codigo": "B-12",
        "duracion_minutos": None,  # la entrada no lleva duracion aunque el acceso ya salio
    }
    assert trazas["actualizacion"]["detalle"] == {
        **trazas["creacion"]["detalle"],
        "duracion_minutos": salida.json()["duracion_minutos"],
    }
    assert trazas["actualizacion"]["detalle"]["duracion_minutos"] is not None
    # lo guardado en la traza no cambia
    assert trazas["creacion"]["valores_nuevos"]["zona_id"] == entrada["zona_id"]


def test_la_entrada_de_visitante_trae_su_tipo(client, admin, identidad, codigos):
    vehiculo = identidad.vehiculo()
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text

    detalle = _trazas_de(client, admin, r.json()["id"])["creacion"]["detalle"]
    assert detalle["placa"] == vehiculo["placa"] and detalle["tipo_acceso"] == "visitante"


def test_con_parqueadero_caido_responde_sin_codigo_de_puesto(client, admin, identidad, codigos, monkeypatch):
    entrada = _entrada_normal(client, admin, identidad, codigos)

    def caido(espacio_ids):
        raise parqueadero_client.ParqueaderoNoDisponibleError("El servicio de parqueadero no esta disponible")

    monkeypatch.setattr(parqueadero_client, "codigos_de_espacios", caido)

    detalle = _trazas_de(client, admin, entrada["acceso"]["id"])["creacion"]["detalle"]
    assert detalle["placa"] == entrada["placa"] and detalle["espacio_codigo"] is None


def test_trazas_que_no_son_de_un_acceso_traen_detalle_null(client, admin, identidad, codigos):
    entrada = _entrada_normal(client, admin, identidad, codigos)
    tabla = f"prueba-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        # solo INSERT: la auditoria es append-only
        sin_acceso = AuditoriaAcceso(
            tabla_afectada="accesos", registro_id=uuid.uuid4(), accion=AccionAuditoria.CREACION,
            realizado_por_id=uuid.uuid4(), valores_nuevos={"zona_id": "x"},
        )
        otra_tabla = AuditoriaAcceso(
            tabla_afectada=tabla, registro_id=uuid.UUID(entrada["acceso"]["id"]),
            accion=AccionAuditoria.ELIMINACION, realizado_por_id=uuid.uuid4(), motivo="cierre de prueba",
        )
        db.add_all([sin_acceso, otra_tabla])
        db.commit()
        sin_acceso_id, otra_tabla_id = str(sin_acceso.id), str(otra_tabla.id)
        registro_al_azar = str(sin_acceso.registro_id)

    traza = _trazas_de(client, admin, registro_al_azar)["creacion"]
    assert traza["id"] == sin_acceso_id and traza["detalle"] is None
    assert traza["valores_nuevos"] == {"zona_id": "x"}

    # aunque registro_id sea un acceso real, solo las trazas de la tabla accesos llevan detalle
    r = client.get(f"{API}/auditoria", headers=admin, params={"tabla_afectada": tabla})
    assert r.status_code == 200, r.text
    [item] = r.json()["items"]
    assert item["id"] == otra_tabla_id and item["detalle"] is None
    assert item["motivo"] == "cierre de prueba" and item["registro_id"] == entrada["acceso"]["id"]


def test_parqueadero_se_consulta_una_vez_por_pagina_con_los_puestos_sin_repetir(client, admin, identidad, codigos):
    espacio_de = {}
    for i in range(60):
        entrada = _entrada_normal(client, admin, identidad, codigos, codigo=f"P-{i:02d}")
        acceso_id = entrada["acceso"]["id"]
        espacio_de[acceso_id] = entrada["espacio_id"]
        assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin).status_code == 200
    codigos.llamadas.clear()

    r = client.get(f"{API}/auditoria", headers=admin, params={"tabla_afectada": "accesos", "por_pagina": 50})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 50 and r.json()["total"] >= 120
    # las 50 mas nuevas son de estos accesos: entrada y salida de cada uno, con el mismo puesto
    assert all(t["registro_id"] in espacio_de for t in items)

    assert len(codigos.llamadas) == 1
    [pedidos] = codigos.llamadas
    assert len(pedidos) == len(set(pedidos))
    assert set(pedidos) == {espacio_de[t["registro_id"]] for t in items}
    assert len(pedidos) < len(items)  # habia repetidos en la pagina
    for t in items:
        assert t["detalle"]["espacio_codigo"] == codigos.nombres[espacio_de[t["registro_id"]]]


def test_una_pagina_sin_trazas_de_accesos_no_consulta_a_parqueadero(client, admin, codigos):
    r = client.get(f"{API}/auditoria", headers=admin, params={"tabla_afectada": f"vacia-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200 and r.json()["items"] == []
    assert codigos.llamadas == []
