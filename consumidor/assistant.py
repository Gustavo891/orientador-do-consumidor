"""Montagem real do assistente: servidores MCP, modelos do OpenRouter, memória em SQLite e o grafo."""

import asyncio
import logging
import os
import sys
import warnings

os.environ.setdefault("FASTMCP_LOG_LEVEL", "WARNING")
warnings.filterwarnings("ignore", message=".*langchain.mcp.*is in beta.*")

import aiosqlite
from langchain.mcp import MCPAdapter
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from . import config, rag
from .graph import RAG_TOOL, Deps, Grade, build_graph, consultar_lei, load_valid_articles, pending_calls
from .guardrails import Scope, mask_pii
from .skills import catalog, make_load_skill, read_skills

log = logging.getLogger("assistente")

SYSTEM_PROMPT = """Você é o Orientador do Consumidor, um assistente que ajuda pessoas comuns no Brasil a entender e exercer seus direitos de consumidor com base no Código de Defesa do Consumidor (CDC, Lei 8.078/1990) e no Decreto 7.962/2013 (comércio eletrônico).

Como trabalhar:
- Antes de afirmar o que a lei diz, use {rag}. Cite só artigos que vieram das ferramentas, no formato (CDC, art. X) ou (Decreto 7.962/2013, art. X).
- Para prazos, datas e valores, use as ferramentas do servidor cdc (cdc_calcular_prazo, cdc_calcular_repeticao_indebito, cdc_verificar_multa_atraso). Nunca calcule de cabeça.
- Para saber a data de hoje, use time_get_current_time com timezone {tz}. Nunca suponha a data.
- Para citar o texto exato de um artigo cujo número você já sabe, use cdc_ler_artigo.
- fetch_fetch só lê páginas de www.gov.br e www.consumidor.gov.br; use quando a pessoa pedir orientação de órgão oficial (Procon, Senacon, consumidor.gov.br).
- Se faltar um dado necessário (data, valor, onde comprou), pergunte em vez de supor.
- Dados pessoais chegam como [CPF removido], [cartão removido] etc. Não peça esses dados.
- Fale em português simples, com frases curtas, e termine com o próximo passo prático. Você orienta, não substitui advogado ou Procon.

Skills disponíveis:
{catalog}

Antes de qualquer outra ferramenta, compare o pedido com as descrições das skills. Se ele corresponder a uma, a sua primeira chamada deve ser load_skill com o nome dela, e você deve seguir os passos e o formato da skill. Perguntas gerais sobre a lei, sem um caso concreto, não precisam de skill."""


def mcp_servers() -> dict:
    return {
        "cdc": {"command": sys.executable, "args": [str(config.SERVER_FILE)]},
        "time": {"command": "uvx", "args": ["mcp-server-time", "--local-timezone", config.TIMEZONE]},
        "fetch": {"command": "uvx", "args": ["mcp-server-fetch", "--allowed-hosts", "www.gov.br", "www.consumidor.gov.br"]},
    }


def structured(schema, fallback):
    model = config.chat_model(reasoning=False).with_structured_output(schema, method="function_calling")

    async def call(prompt: str):
        for _ in range(3):
            try:
                result = await model.ainvoke(prompt)
            except Exception as error:
                log.warning("saída estruturada %s falhou: %s", schema.__name__, error)
                continue
            if result is not None:
                return result
        return fallback

    return call


class Assistant:

    def __init__(self) -> None:
        self.adapter = MCPAdapter({"mcpServers": mcp_servers()})
        self.graph = None
        self.connection = None
        self.mcp_open = False
        self.tool_names: list[str] = []
        self.locks: dict[str, asyncio.Lock] = {}

    async def start(self) -> "Assistant":
        config.api_key()
        if not config.ARTICLES_FILE.exists():
            raise RuntimeError("Índice não encontrado. Rode antes: python -m consumidor.ingest")
        valid_articles = load_valid_articles()
        skills = read_skills()
        try:
            await self.adapter.__aenter__()
            self.mcp_open = True
            mcp_tools = await self.adapter.list_tools()
            load_skill = make_load_skill(skills)
            tools = {t.name: t for t in [*mcp_tools, load_skill]}
            self.tool_names = [RAG_TOOL, *tools]
            self.connection = await aiosqlite.connect(config.MEMORY_FILE)
            deps = Deps(
                agent_model=config.chat_model().bind_tools([consultar_lei, *tools.values()]),
                tools=tools,
                search=rag.search,
                grade=structured(Grade, Grade(suficiente=True, nova_consulta="")),
                classify=structured(Scope, Scope(motivo="classificador indisponível", categoria="consumo")),
                system_prompt=SYSTEM_PROMPT.format(rag=RAG_TOOL, tz=config.TIMEZONE, catalog=catalog(skills)),
                valid_articles=valid_articles,
            )
            self.graph = build_graph(deps, AsyncSqliteSaver(self.connection))
        except BaseException:
            await self.close()
            raise
        return self

    async def close(self) -> None:
        if self.mcp_open:
            self.mcp_open = False
            await self.adapter.__aexit__(None, None, None)
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    async def ask(self, thread_id: str, text: str) -> AIMessage:
        lock = self.locks.setdefault(thread_id, asyncio.Lock())
        async with lock:
            return await self._ask(thread_id, text)

    async def _ask(self, thread_id: str, text: str) -> AIMessage:
        config_ = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
        masked, _ = mask_pii(text)
        try:
            state = await asyncio.wait_for(self.graph.ainvoke({"messages": [HumanMessage(masked)]}, config_), config.TURN_TIMEOUT)
            return state["messages"][-1]
        except TimeoutError:
            log.error("turno excedeu %ss na conversa %s", config.TURN_TIMEOUT, thread_id)
            return await self._recover(config_, "Demorei demais e interrompi a consulta. Pode tentar de novo, talvez com uma pergunta mais curta?", "tempo esgotado no turno")
        except Exception as error:
            log.exception("turno falhou na conversa %s", thread_id)
            return await self._recover(config_, "Tive um problema para responder agora. Pode tentar de novo em instantes?", f"erro no turno: {type(error).__name__}")

    async def _recover(self, config_: dict, text: str, alert: str) -> AIMessage:
        snapshot = await self.graph.aget_state(config_)
        pending = pending_calls(snapshot.values) if snapshot.values.get("messages") else []
        answer = AIMessage(content=text, additional_kwargs={"turno": {"ferramentas": [], "skills": [], "buscas": [], "alertas": [alert]}})
        repairs = [ToolMessage(content="cancelado: o turno foi interrompido", tool_call_id=c["id"], name=c["name"], status="error") for c in pending]
        await self.graph.aupdate_state(config_, {"messages": [*repairs, answer]}, as_node="guarda_saida")
        return answer

    async def history(self, thread_id: str) -> list[AnyMessage]:
        snapshot = await self.graph.aget_state({"configurable": {"thread_id": thread_id}})
        return snapshot.values.get("messages", []) if snapshot.values else []

    async def threads(self, limit: int = 20) -> list[tuple[str, str]]:
        try:
            cursor = await self.connection.execute(
                "SELECT thread_id, MAX(checkpoint_id) FROM checkpoints GROUP BY thread_id ORDER BY 2 DESC LIMIT ?", (limit,)
            )
        except aiosqlite.OperationalError:
            return []
        result = []
        for thread_id, _ in await cursor.fetchall():
            messages = await self.history(thread_id)
            first = next((m.text for m in messages if isinstance(m, HumanMessage)), "(vazia)")
            result.append((thread_id, first))
        return result
