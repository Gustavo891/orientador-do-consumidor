"""Turno interrompido no meio de uma chamada de ferramenta não pode quebrar a conversa."""

import asyncio

from langchain.tools import tool
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from consumidor import config
from consumidor.assistant import Assistant
from consumidor.graph import Deps, build_graph
from consumidor.guardrails import Scope


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


@tool
async def demorada(x: str) -> str:
    """Ferramenta que trava."""
    await asyncio.sleep(10)
    return "nunca"


async def classify(prompt: str) -> Scope:
    return Scope(motivo="t", categoria="consumo")


def make_assistant(model) -> Assistant:
    assistant = object.__new__(Assistant)
    assistant.locks = {}
    deps = Deps(agent_model=model, tools={"demorada": demorada}, search=lambda q: [], grade=None, classify=classify, system_prompt="s", tool_timeout=30)
    assistant.graph = build_graph(deps, InMemorySaver())
    return assistant


def test_turno_interrompido_e_reparado(monkeypatch):
    monkeypatch.setattr(config, "TURN_TIMEOUT", 0.3)
    model = ScriptedModel([
        AIMessage("", tool_calls=[{"name": "demorada", "args": {"x": "1"}, "id": "t1", "type": "tool_call"}]),
        AIMessage("Agora sim."),
    ])
    assistant = make_assistant(model)

    async def scenario():
        first = await assistant.ask("c1", "minha compra deu problema")
        second = await assistant.ask("c1", "e agora?")
        return first, second

    first, second = asyncio.run(scenario())
    assert "interrompi" in first.text
    assert second.text == "Agora sim."
    sent = model.calls[1]
    calls = {c["id"] for m in sent if isinstance(m, AIMessage) for c in m.tool_calls}
    answered = {m.tool_call_id for m in sent if isinstance(m, ToolMessage)}
    assert calls <= answered


def test_cpf_nao_chega_ao_checkpoint():
    model = ScriptedModel([AIMessage("Ok.")])
    assistant = make_assistant(model)

    async def all_checkpoints():
        await assistant.ask("c2", "meu CPF é 123.456.789-09")
        return [s async for s in assistant.graph.aget_state_history({"configurable": {"thread_id": "c2"}})]

    checkpoints = asyncio.run(all_checkpoints())
    assert len(checkpoints) > 3
    assert all("123.456.789-09" not in str(c.values) for c in checkpoints)
