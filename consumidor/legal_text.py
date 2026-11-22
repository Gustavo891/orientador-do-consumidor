"""Leitura do HTML oficial do Planalto e corte em artigos e trechos (mesma lógica do Lab 1)."""

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

ANNOTATION = re.compile(
    r"\((?:Reda[çc][ãa]o dada|Inclu[íi]d[oa]|Revogad[oa]|Vide|Vig[êe]ncia|Regulamento|Produ[çc][ãa]o de efeito)"
    r"[^()]*(?:\([^()]*\)[^()]*)*\)",
    re.I,
)
NOTE = re.compile(r"[IVXL]+ - Dispositivo incluído pela .*?\d{1,2}\.\d{1,2}\.\d{4}(?= [IVXL]+ - )")
HEADING = r"(?:TÍTULO [IVXL]+|CAPÍTULO [IVXL]+(?:-[A-Z])?|SEÇÃO [IVXL]+(?:-[A-Z])?|Art\. ?\d+[º°o]?(?:-[A-Z])?[ .])"
ITEM = r"(?:§ ?\d+[º°o]?|Parágrafo único|[IVXL]+ ?- |[a-z]\) )"
BREAK = re.compile(rf"\s+(?={HEADING})|(?:(?<=[.;:)])|(?<=; e)|(?<=; ou))\s+(?={ITEM})")
VETOED = re.compile(r"(?:[IVXL]+ ?- |§ ?\d+\S* |Parágrafo único\.? |Art\. \S+ |[a-z]\) )?\(?Vetado\)?\s*[.;]?", re.I)
ARTICLE = re.compile(r"^Art\. ?(\d+)[º°o]?(?:-([A-Z]))?\.?\s")


@dataclass(frozen=True)
class Source:
    lei: str
    sigla: str
    arquivo: str
    url: str
    inicio: str
    fim: str


SOURCES = (
    Source("cdc", "CDC", "cdc.htm", "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm", "TÍTULO I", "Brasília, 11 de setembro"),
    Source(
        "decreto_7962",
        "Decreto 7.962/2013",
        "decreto_7962_2013.htm",
        "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7962.htm",
        "Art. 1º",
        "Brasília, 15 de março",
    ),
)


def html_text(path: Path) -> str:
    return BeautifulSoup(path.read_bytes().decode("cp1252"), "lxml").get_text(" ")


def clean(text: str, start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("\xa0", " "))
    text = NOTE.sub("", ANNOTATION.sub("", text))
    text = re.sub(r" +([.,;:])", r"\1", text)
    begin = text.find(start)
    finish = text.find(end, begin)
    text = text[begin : finish if finish > 0 else None]
    lines = [line.strip() for line in BREAK.sub("\n", text).split("\n")]
    return "\n".join(line for line in lines if line and not VETOED.fullmatch(line))


def split_articles(text: str, source: Source) -> list[dict]:
    context = {"titulo": "", "capitulo": "", "secao": ""}
    articles: list[dict] = []
    for line in text.split("\n"):
        if line.startswith("TÍTULO"):
            context = {"titulo": line, "capitulo": "", "secao": ""}
        elif line.startswith("CAPÍTULO"):
            context = {**context, "capitulo": line, "secao": ""}
        elif line.startswith("SEÇÃO"):
            context = {**context, "secao": line}
        elif match := ARTICLE.match(line):
            number = match.group(1) + (f"-{match.group(2)}" if match.group(2) else "")
            articles.append({"artigo": number, "linhas": [line], **context})
        elif articles:
            articles[-1]["linhas"].append(line)
    return [
        {
            "lei": source.lei,
            "sigla": source.sigla,
            "url": source.url,
            "artigo": a["artigo"],
            "fonte": f"{source.sigla}, art. {a['artigo']}",
            "titulo": a["titulo"],
            "capitulo": a["capitulo"],
            "secao": a["secao"],
            "texto": "\n".join(a["linhas"]),
        }
        for a in articles
    ]


def load_articles(raw_dir: Path) -> list[dict]:
    articles: list[dict] = []
    for source in SOURCES:
        text = clean(html_text(raw_dir / source.arquivo), source.inicio, source.fim)
        articles += split_articles(text, source)
    return articles


def chunk_article(article: dict, size: int = 1200, overlap: int = 150) -> list[dict]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap, separators=["\n", "; ", ". ", " "])
    parts = splitter.split_text(article["texto"])
    caput = article["texto"].split("\n")[0]
    place = article["secao"] or article["capitulo"]
    chunks = []
    for i, part in enumerate(parts):
        header = f"[{article['fonte']}] {place}".strip()
        if i > 0:
            header += f"\n(continuação; caput: {caput[:250]})"
        chunks.append(
            {
                "id": f"{article['lei']}-art{article['artigo']}-p{i + 1}",
                "texto": f"{header}\n{part}",
                "metadata": {"lei": article["lei"], "artigo": article["artigo"], "fonte": article["fonte"], "parte": i + 1},
            }
        )
    return chunks
