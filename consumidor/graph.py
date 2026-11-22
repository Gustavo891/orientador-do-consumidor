"""Grafo LangGraph do assistente: guardrails, agente, RAG agêntico e execução de ferramentas."""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Awaitable, Callable, TypedDict

from langchain.tools import tool
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from . import config
from .guardrails import REFUSAL_INJECTION, REFUSAL_SCOPE, SCOPE_PROMPT, Scope, injection_hit, invalid_citations, mask_pii

RAG_TOOL = "consultar_lei"


@tool
def consultar_lei(consulta: str) -> str:
    """Busca trechos do Código de Defesa do Consumidor (CDC) e do Decreto 7.962/2013 (comércio eletrônico).

    Use antes de afirmar o que a lei diz. Escreva a consulta com as palavras da situação e, se souber,
    com termos jurídicos (ex.: 'prazo para reclamar de vício aparente em produto durável'). Se os primeiros
    trechos não bastarem, a busca é refeita automaticamente com outra formulação. Cada trecho começa com
    a fonte para citar, como [CDC, art. 49].
    """
    raise RuntimeError("consultar_lei é executada pelos nós de RAG do grafo, não diretamente.")


class Grade(BaseModel):
    suficiente: bool = Field(description="true se os trechos trazem a regra que responde à pergunta do usuário")
    nova_consulta: str = Field(
        description="se não bastam: nova consulta curta usando as palavras que a lei usaria (ex.: 'venda casada' -> "
        "'condicionar o fornecimento de produto ao fornecimento de outro'; 'nome sujo' -> 'cadastro de consumidores informações negativas'). "
        "Vazio se bastam."
    )


GRADE_PROMPT = """Você avalia se trechos de lei recuperados respondem à pergunta de um consumidor.

PERGUNTA DO USUÁRIO: {pergunta}
CONSULTA USADA: {consulta}
CONSULTAS JÁ TENTADAS: {tentadas}

TRECHOS:
{trechos}

Diga se algum trecho traz a regra que responde à pergunta. Se nenhum traz, proponha uma nova consulta diferente das já tentadas."""


class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    consulta: str
    tentativas_busca: int
    trechos: list[dict]
    avaliacao: dict
    buscas_turno: list[str]
    ferramentas_turno: list[str]
    skills_turno: list[str]
    alertas: list[str]


@dataclass(frozen=True)
class Deps:
    agent_model: Any
    tools: dict[str, BaseTool]
    search: Callable[[str], list[dict]]
    grade: Callable[[str], Awaitable[Grade]]
    classify: Callable[[str], Awaitable[Scope]]
    system_prompt: str
    valid_articles: set[tuple[str, str]] = field(default_factory=set)
    max_searches: int = config.MAX_SEARCHES
    tool_timeout: float = config.TOOL_TIMEOUT


def last_human(state: State) -> HumanMessage | None:
    return next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)


def pending_calls(state: State) -> list[dict]:
    messages = state["messages"]
    index = next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], AIMessage)), None)
    if index is None:
        return []
    answered = {m.tool_call_id for m in messages[index + 1 :] if isinstance(m, ToolMessage)}
    return [c for c in messages[index].tool_calls if c["id"] not in answered]


def turn_meta(state: State) -> dict:
    return {
        "ferramentas": state.get("ferramentas_turno", []),
        "skills": state.get("skills_turno", []),
        "buscas": state.get("buscas_turno", []),
        "alertas": state.get("alertas", []),
    }


def format_chunks(chunks: list[dict]) -> str:
    return "\n\n".join(f"Trecho {i + 1} (distância {c['distancia']}):\n{c['texto']}" for i, c in enumerate(chunks))


def build_graph(deps: Deps, checkpointer=None):
    async def guarda_entrada(state: State) -> State:
        message = state["messages"][-1]
        update: State = {"ferramentas_turno": [], "skills_turno": [], "buscas_turno": [], "alertas": [], "tentativas_busca": 0, "trechos": []}
        masked, found = mask_pii(message.text)
        found = list(dict.fromkeys(found + re.findall(r"\[(CPF|cartão|e-mail|telefone) removido\]", masked)))
        if masked != message.text:
            update["messages"] = [HumanMessage(content=masked, id=message.id)]
        if found:
            update["alertas"] = [f"dados pessoais removidos da mensagem antes de enviar ao modelo: {', '.join(found)}"]
        if injection_hit(masked):
            refusal, reason = REFUSAL_INJECTION, "entrada bloqueada: tentativa de prompt injection (regex)"
        else:
            previous = next((m.text for m in reversed(state["messages"][:-1]) if isinstance(m, AIMessage) and m.text), "(nenhuma)")

            scope = await deps.classify(SCOPE_PROMPT.format(anterior=previous[:400], mensagem=masked))
            refusal, reason = {
                "injecao": (REFUSAL_INJECTION, "entrada bloqueada: tentativa de prompt injection (classificador)"),
                "fora_do_escopo": (REFUSAL_SCOPE, "entrada bloqueada: fora do escopo"),
            }.get(scope.categoria, (None, None))
        if refusal:
            alerts = update["alertas"] + [reason]
            meta = {"ferramentas": [], "skills": [], "buscas": [], "alertas": alerts, "bloqueado": True}
            update["alertas"] = alerts
            update["messages"] = update.get("messages", []) + [AIMessage(content=refusal, additional_kwargs={"turno": meta})]
        return update

    async def agente(state: State) -> State:
        response = await deps.agent_model.ainvoke([SystemMessage(deps.system_prompt), *state["messages"]])
        return {"messages": [response]}

    async def buscar(state: State) -> State:
        call = next(c for c in pending_calls(state) if c["name"] == RAG_TOOL)
        attempt = state.get("tentativas_busca", 0)
        query = state["consulta"] if attempt else str(call["args"].get("consulta", "")).strip()
        query = query or (last_human(state).text if last_human(state) else "")
        try:
            chunks = await asyncio.to_thread(deps.search, query)
        except Exception as error:
            chunks = [{"fonte": "erro", "distancia": 1.0, "texto": f"ERRO na busca: {error}"}]
        return {"consulta": query, "trechos": chunks, "buscas_turno": [*state.get("buscas_turno", []), query]}

    async def avaliar(state: State) -> State:
        human = last_human(state)
        grade = await deps.grade(
            GRADE_PROMPT.format(
                pergunta=human.text if human else "",
                consulta=state["consulta"],
                tentadas="; ".join(state.get("buscas_turno", [])),
                trechos="\n\n".join(f"[{c['fonte']}] {c['texto'][:500]}" for c in state["trechos"]),
            )
        )
        return {"avaliacao": grade.model_dump()}

    async def reformular(state: State) -> State:
        new_query = state["avaliacao"].get("nova_consulta", "").strip() or f"{state['consulta']} direitos do consumidor"
        return {"consulta": new_query, "tentativas_busca": state.get("tentativas_busca", 0) + 1}

    async def responder_busca(state: State) -> State:
        call = next(c for c in pending_calls(state) if c["name"] == RAG_TOOL)
        enough = state["avaliacao"].get("suficiente", False)
        note = "" if enough else (
            "\n\nAVISO: após várias reformulações, nenhum trecho pareceu responder à pergunta. "
            "Não invente: diga o que a lei consultada não cobre ou peça mais detalhes."
        )
        content = f"Consultas feitas: {' | '.join(state.get('buscas_turno', []))}\n\n{format_chunks(state['trechos'])}{note}"
        return {
            "messages": [ToolMessage(content=content, tool_call_id=call["id"], name=RAG_TOOL)],
            "ferramentas_turno": [*state.get("ferramentas_turno", []), RAG_TOOL],
            "tentativas_busca": 0,
        }

    async def ferramentas(state: State) -> State:
        messages, used, skills = [], list(state.get("ferramentas_turno", [])), list(state.get("skills_turno", []))
        for call in [c for c in pending_calls(state) if c["name"] != RAG_TOOL]:
            used.append(call["name"])
            if call["name"] == "load_skill":
                skills.append(str(call["args"].get("name", "")))
            tool_ = deps.tools.get(call["name"])
            if tool_ is None:
                messages.append(ToolMessage(content=f"ERRO: ferramenta {call['name']} não existe.", tool_call_id=call["id"], name=call["name"], status="error"))
                continue
            try:
                result = await asyncio.wait_for(tool_.ainvoke({**call, "type": "tool_call"}), deps.tool_timeout)
                messages.append(result if isinstance(result, ToolMessage) else ToolMessage(content=str(result), tool_call_id=call["id"], name=call["name"]))
            except TimeoutError:
                messages.append(ToolMessage(content=f"ERRO: {call['name']} não respondeu em {deps.tool_timeout:.0f}s.", tool_call_id=call["id"], name=call["name"], status="error"))
            except Exception as error:
                messages.append(ToolMessage(content=f"ERRO: {error}", tool_call_id=call["id"], name=call["name"], status="error"))
        return {"messages": messages, "ferramentas_turno": used, "skills_turno": skills}

    async def guarda_saida(state: State) -> State:
        answer = state["messages"][-1]
        text = answer.text or "Desculpe, não consegui montar uma resposta. Pode reformular a pergunta?"
        alerts = list(state.get("alertas", []))
        text, found = mask_pii(text)
        if found:
            alerts.append(f"dados pessoais removidos da resposta: {', '.join(found)}")
        bad = invalid_citations(text, deps.valid_articles)
        if bad:
            alerts.append(f"citação não verificada: {'; '.join(bad)}")
            text += (
                "\n\n*Atenção: esta resposta cita " + "; ".join(bad) + ", que não está no CDC nem no Decreto 7.962/2013 "
                "consultados por este assistente. Confira essa referência antes de usá-la.*"
            )
        meta = {**turn_meta(state), "alertas": alerts}
        return {"messages": [AIMessage(content=text, id=answer.id, additional_kwargs={"turno": meta})], "alertas": alerts}

    def depois_entrada(state: State) -> str:
        return END if isinstance(state["messages"][-1], AIMessage) else "agente"

    def depois_agente(state: State) -> str:
        pending = pending_calls(state)
        if not pending:
            return "guarda_saida"
        return "buscar" if any(c["name"] == RAG_TOOL for c in pending) else "ferramentas"

    def depois_avaliar(state: State) -> str:
        done = state["avaliacao"].get("suficiente") or state.get("tentativas_busca", 0) + 1 >= deps.max_searches
        return "responder_busca" if done else "reformular"

    def depois_ferramenta(state: State) -> str:
        pending = pending_calls(state)
        if any(c["name"] == RAG_TOOL for c in pending):
            return "buscar"
        return "ferramentas" if pending else "agente"

    builder = StateGraph(State)
    for name, node in [
        ("guarda_entrada", guarda_entrada), ("agente", agente), ("buscar", buscar), ("avaliar", avaliar),
        ("reformular", reformular), ("responder_busca", responder_busca), ("ferramentas", ferramentas), ("guarda_saida", guarda_saida),
    ]:
        builder.add_node(name, node)
    builder.add_edge(START, "guarda_entrada")
    builder.add_conditional_edges("guarda_entrada", depois_entrada, ["agente", END])
    builder.add_conditional_edges("agente", depois_agente, ["buscar", "ferramentas", "guarda_saida"])
    builder.add_edge("buscar", "avaliar")
    builder.add_conditional_edges("avaliar", depois_avaliar, ["reformular", "responder_busca"])
    builder.add_edge("reformular", "buscar")
    builder.add_conditional_edges("responder_busca", depois_ferramenta, ["buscar", "ferramentas", "agente"])
    builder.add_conditional_edges("ferramentas", depois_ferramenta, ["buscar", "ferramentas", "agente"])
    builder.add_edge("guarda_saida", END)
    return builder.compile(checkpointer=checkpointer)


def valid_articles_from(articles: list[dict]) -> set[tuple[str, str]]:
    return {(a["lei"], a["artigo"]) for a in articles}


def load_valid_articles() -> set[tuple[str, str]]:
    return valid_articles_from(json.loads(config.ARTICLES_FILE.read_text(encoding="utf-8")))
