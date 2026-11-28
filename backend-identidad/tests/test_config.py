"""Claves del servicio (seguridad S1): SECRET_KEY y CLAVE_INTERNA no aceptan la clave de ejemplo ni
una de menos de 32 caracteres, y el error no muestra el valor. No usa la base de datos."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = "postgresql+psycopg://usuario:clave@localhost:5432/base"
BUENA = "a" * 32
EJEMPLOS = {"SECRET_KEY": "cambiar-esta-clave-en-produccion", "CLAVE_INTERNA": "cambiar-esta-clave-interna"}


# Configuracion sin .env, con las claves dadas.
def _settings(**claves) -> Settings:
    valores = {"DATABASE_URL": BASE, "SECRET_KEY": BUENA, "CLAVE_INTERNA": BUENA, **claves}
    return Settings(_env_file=None, **valores)


@pytest.mark.parametrize("campo", ["SECRET_KEY", "CLAVE_INTERNA"])
@pytest.mark.parametrize("tipo", ["ejemplo", "corta"])
def test_rechaza_la_clave_de_ejemplo_o_corta_sin_mostrarla(campo, tipo):
    valor = EJEMPLOS[campo] if tipo == "ejemplo" else "b" * 31
    with pytest.raises(ValidationError) as error:
        _settings(**{campo: valor})
    texto = str(error.value)
    assert f"{campo} no puede ser la clave de ejemplo ni tener menos de 32 caracteres" in texto
    assert "openssl rand -hex 32" in texto
    assert valor not in texto


def test_acepta_claves_de_32_caracteres():
    settings = _settings(SECRET_KEY="c" * 32, CLAVE_INTERNA="d" * 32)
    assert settings.SECRET_KEY == "c" * 32 and settings.CLAVE_INTERNA == "d" * 32


def test_clave_interna_no_tiene_valor_por_defecto(monkeypatch):
    monkeypatch.delenv("CLAVE_INTERNA", raising=False)
    with pytest.raises(ValidationError, match="CLAVE_INTERNA"):
        Settings(_env_file=None, DATABASE_URL=BASE, SECRET_KEY=BUENA)
