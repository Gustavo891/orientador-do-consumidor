"""Interface Streamlit do Orientador do Consumidor."""

import logging
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from consumidor.assistant import Assistant
from consumidor.runtime import BackgroundLoop

logging.getLogger("fastmcp").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)

st.set_page_config(page_title="Orientador do Consumidor", page_icon="⚖️", layout="centered")

EXAMPLES = [
    "Comprei um celular pelo site e recebi dia 15/11/2026. Me arrependi, ainda dá tempo de devolver?",
    "Paguei R$ 89,90 duas vezes na mesma fatura por uma assinatura. Quanto posso pedir de volta?",
    "Recebi um cartão de crédito que não pedi e querem cobrar anuidade. Tenho que pagar?",
]


@st.cache_resource(show_spinner="Conectando aos servidores MCP...")
def runtime() -> tuple[BackgroundLoop, Assistant]:
    loop = BackgroundLoop()
    assistant = loop.run(Assistant().start())
    return loop, assistant


def new_conversation() -> None:
    st.session_state.thread_id = f"conversa-{uuid.uuid4().hex[:8]}"


def show_turn(meta: dict) -> None:
    tools, skills, searches, alerts = (meta.get(k) or [] for k in ("ferramentas", "skills", "buscas", "alertas"))
    label = f"🔧 {len(tools)} ferramenta(s) · 📘 {len(skills)} skill(s)" + (f" · ⚠️ {len(alerts)} alerta(s)" if alerts else "")
    with st.expander(label):
        st.markdown("**Ferramentas chamadas:** " + (", ".join(f"`{t}`" for t in tools) or "nenhuma"))
        st.markdown("**Skills carregadas:** " + (", ".join(f"`{s}`" for s in skills) or "nenhuma"))
        if searches:
            st.markdown("**Consultas à lei (RAG):**\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(searches, 1)))
        for alert in alerts:
            st.warning(alert)


def render(messages) -> None:
    for message in messages:
        if isinstance(message, HumanMessage):
            st.chat_message("user").markdown(message.text)
        elif isinstance(message, AIMessage) and not message.tool_calls and message.text:
            with st.chat_message("assistant"):
                st.markdown(message.text.replace("\n", "  \n"))
                if "turno" in message.additional_kwargs:
                    show_turn(message.additional_kwargs["turno"])


loop, assistant = runtime()
if "thread_id" not in st.session_state:
    new_conversation()

with st.sidebar:
    st.title("⚖️ Orientador do Consumidor")
    st.caption("Direitos do consumidor com base no CDC e no Decreto 7.962/2013. Orienta, não substitui advogado ou Procon.")
    st.button("➕ Nova conversa", on_click=new_conversation, use_container_width=True)
    st.subheader("Conversas")
    for thread_id, title in loop.run(assistant.threads()):
        current = thread_id == st.session_state.thread_id
        if st.button(("▶ " if current else "") + title[:40], key=thread_id, use_container_width=True, disabled=current):
            st.session_state.thread_id = thread_id
            st.rerun()

history = loop.run(assistant.history(st.session_state.thread_id))
if not history:
    st.markdown("### Como posso ajudar?\nConte o seu problema de consumo. Exemplos:")
    for example in EXAMPLES:
        st.markdown(f"- {example}")
render(history)

if prompt := st.chat_input("Descreva o seu problema de consumo"):
    st.chat_message("user").markdown(prompt)
    with st.chat_message("assistant"), st.spinner("Consultando a lei e as ferramentas..."):
        answer = loop.run(assistant.ask(st.session_state.thread_id, prompt))
    st.rerun()
