"""Servidor MCP "cdc": texto oficial dos artigos e cálculos de prazos e valores do CDC."""

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Literal

os.environ.setdefault("FASTMCP_LOG_LEVEL", "WARNING")

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError
from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from consumidor import rules as cdc_tools

ARTICLES = {(a["lei"], a["artigo"]): a for a in json.loads((ROOT / "data" / "artigos.json").read_text(encoding="utf-8"))}

Lei = Literal["cdc", "decreto_7962"]
TipoPrazo = Literal[
    "arrependimento",
    "vicio_aparente_nao_duravel",
    "vicio_aparente_duravel",
    "vicio_oculto_nao_duravel",
    "vicio_oculto_duravel",
    "conserto_pelo_fornecedor",
    "reparacao_de_danos",
]

mcp = FastMCP(
    "cdc",
    instructions=(
        "Direitos do consumidor no Brasil: texto integral dos artigos do Código de Defesa do Consumidor "
        "(Lei 8.078/1990) e do Decreto 7.962/2013 (comércio eletrônico) e cálculo de prazos e valores."
    ),
)


@mcp.tool
def ler_artigo(
    numero: Annotated[str, Field(description="Número do artigo, só o número e a letra se houver: '49', '26', '54-A'. Sem 'art.' nem '§'.")],
    lei: Annotated[Lei, Field(description="'cdc' para o Código de Defesa do Consumidor ou 'decreto_7962' para o decreto do comércio eletrônico.")] = "cdc",
) -> dict:
    """Devolve o texto integral e oficial de um artigo, com todos os parágrafos e incisos.

    Use quando já se sabe o número do artigo (por exemplo, depois de uma busca na lei ou de
    calcular_prazo, que informa a base legal) e é preciso citar o texto exato.
    """
    key = (lei, numero.strip().upper().removeprefix("ART.").strip().rstrip("ºo°."))
    if key not in ARTICLES:
        raise ToolError(f"Artigo {numero} não encontrado em {lei}. Pode ter sido vetado ou não existir; faça uma busca na lei.")
    article = ARTICLES[key]
    return {"fonte": article["fonte"], "secao": article["secao"] or article["capitulo"], "texto": article["texto"], "url": article["url"]}


@mcp.tool
def calcular_prazo(
    tipo: Annotated[TipoPrazo, Field(description="Qual prazo do CDC. Veja o recurso cdc://prazos para saber quando usar cada um.")],
    data_inicio: Annotated[str, Field(description="Data em que o prazo começa, no formato AAAA-MM-DD (ex.: data de recebimento do produto).")],
    data_referencia: Annotated[str, Field(description="Data em que se quer saber se o prazo está aberto, AAAA-MM-DD. Normalmente a data de hoje no fuso do consumidor: obtenha com uma ferramenta de data e hora, não suponha.")],
) -> dict:
    """Calcula a data-limite de um prazo do consumidor e diz se ainda está dentro do prazo.

    Prazos: arrependimento de compra fora da loja (7 dias), reclamação de vício aparente ou
    oculto em produto não durável (30 dias) ou durável (90 dias), conserto pelo fornecedor
    (30 dias) e ação de reparação de danos (5 anos). Conta dias corridos, sem o dia do início.
    Devolve data_limite, dias_restantes, dentro_do_prazo e a base legal para citar.
    """
    try:
        return cdc_tools.calcular_prazo(tipo, data_inicio, data_referencia)
    except ValueError as error:
        raise ToolError(str(error)) from None


@mcp.tool
def calcular_repeticao_indebito(
    valor_pago: Annotated[float, Field(description="Quanto o consumidor efetivamente pagou, em reais.")],
    valor_devido: Annotated[float, Field(description="Quanto era realmente devido, em reais (0 se nada era devido).")],
) -> dict:
    """Calcula quanto o consumidor tem a receber por uma cobrança indevida que já pagou.

    Pelo CDC, art. 42, parágrafo único, a devolução é o dobro do que foi pago em excesso,
    mais correção e juros. Use quando o consumidor pagou uma cobrança a mais ou indevida.
    """
    try:
        return cdc_tools.calcular_repeticao_indebito(valor_pago, valor_devido)
    except ValueError as error:
        raise ToolError(str(error)) from None


@mcp.tool
def verificar_multa_atraso(
    valor_prestacao: Annotated[float, Field(description="Valor da parcela ou prestação em atraso, em reais.")],
    multa_cobrada: Annotated[float, Field(description="Valor da multa por atraso cobrada, em reais (não os juros).")],
) -> dict:
    """Confere se a multa por atraso de uma prestação passa do limite legal de 2% (CDC, art. 52, § 1º).

    Use em financiamentos, crediários e compras parceladas. Devolve a multa máxima permitida,
    se a cobrada é abusiva e o excesso.
    """
    try:
        return cdc_tools.verificar_multa_atraso(valor_prestacao, multa_cobrada)
    except ValueError as error:
        raise ToolError(str(error)) from None


@mcp.resource("cdc://prazos", mime_type="application/json")
def prazos() -> str:
    """Tabela dos prazos do consumidor: duração, quando usar, a partir de quando conta e base legal."""
    return json.dumps(cdc_tools.PRAZOS, ensure_ascii=False, indent=2)


@mcp.resource("cdc://artigo/{lei}/{numero}", mime_type="text/plain")
def artigo(lei: str, numero: str) -> str:
    """Texto integral de um artigo, para anexar ao contexto. Ex.: cdc://artigo/cdc/49."""
    article = ARTICLES.get((lei, numero))
    if article is None:
        raise ResourceError(f"artigo {numero} não encontrado em {lei}")
    return f"{article['fonte']}\n{article['texto']}"


@mcp.prompt
def reclamacao_formal(produto: str, problema: str, loja: str, data_compra: str) -> str:
    """Pede uma reclamação por escrito ao fornecedor, fundamentada no CDC e pronta para enviar."""
    return (
        f"Escreva uma reclamação formal à empresa {loja} sobre o produto {produto}, comprado em {data_compra}.\n"
        f"Problema relatado pelo consumidor: {problema}\n\n"
        "Antes de escrever, busque a base legal na lei e calcular_prazo para conferir se a "
        "reclamação está no prazo. A carta deve ter: identificação do pedido, descrição objetiva do problema, "
        "os artigos do CDC que garantem o direito (citados como 'CDC, art. X'), o pedido concreto (troca, conserto, "
        "devolução do dinheiro ou abatimento), um prazo de resposta de 10 dias e a menção de que, sem solução, o "
        "consumidor procurará o Procon ou o consumidor.gov.br. Não invente dados que o consumidor não informou."
    )


if __name__ == "__main__":
    mcp.run(show_banner=False)
