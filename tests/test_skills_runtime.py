import asyncio

from consumidor.runtime import BackgroundLoop
from consumidor.skills import catalog, make_load_skill, read_skills


def test_le_as_duas_skills_do_projeto():
    skills = read_skills()
    assert set(skills) == {"verificar-prazo", "analisar-cobranca"}
    assert all(info["description"] and info["body"] for info in skills.values())


def test_catalogo_tem_nome_e_descricao():
    text = catalog(read_skills())
    assert text.count("\n- ") == 1 and "- verificar-prazo:" in text


def test_load_skill_devolve_corpo_e_trata_nome_errado():
    load_skill = make_load_skill(read_skills())
    assert "cdc_calcular_prazo" in load_skill.invoke({"name": "verificar-prazo"})
    assert "não existe" in load_skill.invoke({"name": "inexistente"})


def test_skill_cita_ferramentas_que_existem():
    body = read_skills()["verificar-prazo"]["body"]
    for name in ["time_get_current_time", "cdc_calcular_prazo", "cdc_ler_artigo"]:
        assert name in body


def test_laco_em_segundo_plano_executa_corrotinas():
    loop = BackgroundLoop()

    async def soma(a, b):
        await asyncio.sleep(0.01)
        return a + b

    assert loop.run(soma(2, 3)) == 5
    assert loop.thread.is_alive()
