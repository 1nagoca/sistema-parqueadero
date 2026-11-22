"""Pruebas del paso 3 del pipeline: formato de placa colombiana y venezolana de moto."""

import pytest

from app.pipeline.postprocess import es_placa_valida, seleccionar_mejor_candidato


@pytest.mark.parametrize("placa", ["ABC12", "ABC12D", "AB1C23D"])
def test_placas_validas(placa):
    assert es_placa_valida(placa)


@pytest.mark.parametrize("placa", ["ABC123", "AB12C3D", "ABC12DE", "AB1C23"])
def test_placas_invalidas(placa):
    assert not es_placa_valida(placa)


def test_candidato_venezolano_se_normaliza():
    assert seleccionar_mejor_candidato([("ab-1c 23d", 0.9)]) == ("AB1C23D", 0.9)


def test_descarta_ruido_aunque_tenga_mas_confianza():
    assert seleccionar_mejor_candidato([("UFPS", 0.95), ("ab-1c 23d", 0.8)]) == ("AB1C23D", 0.8)
