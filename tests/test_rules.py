import pytest

from consumidor.rules import PRAZOS, calcular_prazo, calcular_repeticao_indebito, verificar_multa_atraso


def test_arrependimento_conta_sete_dias_corridos():
    result = calcular_prazo("arrependimento", "2026-11-10", "2026-11-15")
    assert result["data_limite"] == "2026-11-17"
    assert result["dias_restantes"] == 2
    assert result["dentro_do_prazo"] is True
    assert result["base_legal"] == "CDC, art. 49"


def test_ultimo_dia_ainda_esta_no_prazo():
    result = calcular_prazo("arrependimento", "2026-11-10", "2026-11-17")
    assert result["dentro_do_prazo"] is True
    assert result["dias_restantes"] == 0


def test_prazo_vencido():
    result = calcular_prazo("vicio_aparente_nao_duravel", "2026-09-01", "2026-11-20")
    assert result["data_limite"] == "2026-10-01"
    assert result["dentro_do_prazo"] is False
    assert result["dias_restantes"] == 0


def test_vicio_duravel_noventa_dias():
    assert calcular_prazo("vicio_aparente_duravel", "2026-01-01", "2026-01-02")["data_limite"] == "2026-04-01"


def test_reparacao_cinco_anos_em_29_de_fevereiro():
    assert calcular_prazo("reparacao_de_danos", "2024-02-29", "2024-03-01")["data_limite"] == "2029-02-28"


@pytest.mark.parametrize(
    "args",
    [
        ("garantia_estendida", "2026-01-01", "2026-01-02"),
        ("arrependimento", "10/11/2026", "2026-11-20"),
        ("arrependimento", "2026-12-01", "2026-11-20"),
    ],
)
def test_calcular_prazo_rejeita_entrada_invalida(args):
    with pytest.raises(ValueError):
        calcular_prazo(*args)


def test_todos_os_tipos_calculam():
    for tipo in PRAZOS:
        assert calcular_prazo(tipo, "2026-01-01", "2026-01-01")["dentro_do_prazo"]


def test_repeticao_do_indebito_em_dobro():
    result = calcular_repeticao_indebito(valor_pago=350.0, valor_devido=200.0)
    assert result["pago_em_excesso"] == 150.0
    assert result["devolucao_em_dobro"] == 300.0


@pytest.mark.parametrize("pago,devido", [(100.0, 100.0), (50.0, 100.0), (-1.0, 0.0)])
def test_repeticao_sem_excesso_e_erro(pago, devido):
    with pytest.raises(ValueError):
        calcular_repeticao_indebito(pago, devido)


def test_multa_acima_de_dois_por_cento_e_abusiva():
    result = verificar_multa_atraso(valor_prestacao=500.0, multa_cobrada=50.0)
    assert result["multa_maxima_permitida"] == 10.0
    assert result["abusiva"] is True
    assert result["excesso"] == 40.0
    assert result["percentual_cobrado"] == 10.0


def test_multa_no_limite_nao_e_abusiva():
    assert verificar_multa_atraso(500.0, 10.0)["abusiva"] is False


@pytest.mark.parametrize("prestacao,multa", [(0.0, 1.0), (100.0, -1.0)])
def test_multa_rejeita_valores_invalidos(prestacao, multa):
    with pytest.raises(ValueError):
        verificar_multa_atraso(prestacao, multa)
