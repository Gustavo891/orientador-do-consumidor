"""Conversa pelo terminal, sem Streamlit (útil para testar o grafo real)."""

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("MEMORY_FILE", str(Path(__file__).resolve().parent.parent / "data" / "memoria_testes.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from consumidor.assistant import Assistant


async def main(messages: list[str]) -> None:
    assistant = await Assistant().start()
    thread = f"cli-{uuid.uuid4().hex[:8]}"
    try:
        for text in messages:
            answer = await assistant.ask(thread, text)
            meta = answer.additional_kwargs.get("turno", {})
            print(f"\n>>> {text}\n{answer.text}\n[ferramentas: {meta.get('ferramentas')} | skills: {meta.get('skills')} | buscas: {meta.get('buscas')} | alertas: {meta.get('alertas')}]")
    finally:
        await assistant.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main(sys.argv[1:]))
