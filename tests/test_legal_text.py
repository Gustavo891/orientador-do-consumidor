from pathlib import Path

import pytest

from consumidor.legal_text import SOURCES, chunk_article, clean, load_articles

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.fixture(scope="module")
def articles():
    return load_articles(RAW)


def test_conta_artigos_de_cada_lei(articles):
    by_law = {}
    for a in articles:
        by_law[a["lei"]] = by_law.get(a["lei"], 0) + 1
    assert by_law == {"cdc": 118, "decreto_7962": 9}


def test_artigo_26_tem_prazos_e_nao_tem_veto(articles):
    art26 = next(a for a in articles if a["fonte"] == "CDC, art. 26")
    assert "trinta dias" in art26["texto"] and "noventa dias" in art26["texto"]
    assert "Vetado" not in art26["texto"]
    assert art26["secao"].startswith("SEÇÃO IV")


def test_limpeza_remove_anotacoes_e_nota_do_art_39(articles):
    text = "\n".join(a["texto"] for a in articles)
    assert "Redação dada" not in text and "Incluído pela" not in text
    assert "Dispositivo incluído" not in text


def test_artigos_com_letra(articles):
    assert any(a["fonte"] == "CDC, art. 54-A" for a in articles)


def test_clean_nao_quebra_em_citacao_interna():
    text = "Art. 1º Texto. § 2º As dívidas referidas no § 1º deste artigo englobam tudo."
    assert clean(text, "Art. 1º", "FIM").split("\n") == ["Art. 1º Texto.", "§ 2º As dívidas referidas no § 1º deste artigo englobam tudo."]


def test_chunk_de_artigo_longo_repete_fonte_e_caput(articles):
    art39 = next(a for a in articles if a["fonte"] == "CDC, art. 39")
    chunks = chunk_article(art39)
    assert len(chunks) > 1
    assert all(c["texto"].startswith("[CDC, art. 39]") for c in chunks)
    assert "caput: Art. 39. É vedado" in chunks[1]["texto"]
    assert [c["id"] for c in chunks] == [f"cdc-art39-p{i}" for i in range(1, len(chunks) + 1)]


def test_fontes_tem_url_oficial():
    assert all(s.url.startswith("https://www.planalto.gov.br/") for s in SOURCES)
