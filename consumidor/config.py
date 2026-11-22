"""Caminhos, modelos e chaves. A chave da API vem do ambiente ou de um `.env` na raiz do projeto."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
ARTICLES_FILE = DATA_DIR / "artigos.json"
INDEX_DIR = DATA_DIR / "chroma"
MEMORY_FILE = Path(os.environ.get("MEMORY_FILE", DATA_DIR / "memoria.sqlite"))
SKILLS_DIR = ROOT / "skills"
SERVER_FILE = ROOT / "servers" / "cdc_server.py"

OPENROUTER_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen/qwen3.7-flash")
EMBEDDING_MODEL = "openai/text-embedding-3-small"
COLLECTION = "cdc_artigos"
TIMEZONE = "America/Sao_Paulo"

RETRIEVAL_K = 6
MAX_SEARCHES = 3


def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Defina OPENROUTER_API_KEY no ambiente ou no arquivo .env (veja .env.example).")
    return key


TOOL_TIMEOUT = 60
TURN_TIMEOUT = 240


def chat_model(reasoning: bool = True, **kwargs):
    from langchain.chat_models import init_chat_model

    if not reasoning:
        kwargs["extra_body"] = {"reasoning": {"enabled": False}}
    return init_chat_model(f"openai:{CHAT_MODEL}", base_url=OPENROUTER_URL, api_key=api_key(), temperature=0.0, timeout=90, max_retries=1, **kwargs)


def embeddings():
    from langchain.embeddings import init_embeddings

    return init_embeddings(f"openai:{EMBEDDING_MODEL}", base_url=OPENROUTER_URL, api_key=api_key(), check_embedding_ctx_length=False)
