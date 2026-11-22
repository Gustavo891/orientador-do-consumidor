"""Índice vetorial dos artigos (Chroma) e busca com distância."""

from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def vectorstore():
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=config.COLLECTION,
        embedding_function=config.embeddings(),
        persist_directory=str(config.INDEX_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


def search(query: str, k: int = config.RETRIEVAL_K) -> list[dict]:
    results = vectorstore().similarity_search_with_score(query, k=k)
    return [{"fonte": doc.metadata["fonte"], "distancia": round(score, 3), "texto": doc.page_content} for doc, score in results]
