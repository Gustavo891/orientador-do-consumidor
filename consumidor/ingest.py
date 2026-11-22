"""Cria `data/artigos.json` e o índice `data/chroma/` a partir do HTML oficial em `data/raw/`."""

import json
import logging
import urllib.request

from . import config
from .legal_text import SOURCES, chunk_article, load_articles

log = logging.getLogger("ingest")


def download_missing() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        path = config.RAW_DIR / source.arquivo
        if path.exists():
            continue
        log.info("baixando %s", source.url)
        request = urllib.request.Request(source.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    download_missing()
    articles = load_articles(config.RAW_DIR)
    config.ARTICLES_FILE.write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("%d artigos gravados em %s", len(articles), config.ARTICLES_FILE)

    from langchain_core.documents import Document

    from .rag import vectorstore

    chunks = [chunk for article in articles for chunk in chunk_article(article)]
    store = vectorstore()
    existing = set(store.get(ids=[c["id"] for c in chunks])["ids"])
    new = [c for c in chunks if c["id"] not in existing]
    if new:
        store.add_documents([Document(page_content=c["texto"], metadata=c["metadata"]) for c in new], ids=[c["id"] for c in new])
    log.info("%d trechos já estavam no índice, %d adicionados (total %d)", len(existing), len(new), store._collection.count())


if __name__ == "__main__":
    main()
