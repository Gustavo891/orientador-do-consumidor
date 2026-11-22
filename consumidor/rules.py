"""Regras de prazo e de valores do Código de Defesa do Consumidor."""

from datetime import date, timedelta

PRAZOS: dict[str, dict] = {
    "arrependimento": {
        "dias": 7,
        "base_legal": "CDC, art. 49",
        "quando_usar": "desistir de compra feita fora da loja física (internet, telefone, catálogo, em casa), mesmo sem defeito",
        "conta_a_partir_de": "assinatura do contrato ou recebimento do produto, o que for depois",
    },
    "vicio_aparente_nao_duravel": {
        "dias": 30,
        "base_legal": "CDC, art. 26, I e § 1º",
        "quando_usar": "reclamar de defeito visível ou fácil de notar em produto ou serviço não durável (alimento, cosmético, lavagem de carro)",
        "conta_a_partir_de": "entrega efetiva do produto ou fim da execução do serviço",
    },
    "vicio_aparente_duravel": {
        "dias": 90,
        "base_legal": "CDC, art. 26, II e § 1º",
        "quando_usar": "reclamar de defeito visível ou fácil de notar em produto ou serviço durável (eletrodoméstico, celular, móvel, reforma)",
        "conta_a_partir_de": "entrega efetiva do produto ou fim da execução do serviço",
    },
    "vicio_oculto_nao_duravel": {
        "dias": 30,
        "base_legal": "CDC, art. 26, I e § 3º",
        "quando_usar": "reclamar de defeito escondido, que só apareceu com o uso, em produto ou serviço não durável",
        "conta_a_partir_de": "dia em que o defeito ficou evidente",
    },
    "vicio_oculto_duravel": {
        "dias": 90,
        "base_legal": "CDC, art. 26, II e § 3º",
        "quando_usar": "reclamar de defeito escondido, que só apareceu com o uso, em produto ou serviço durável",
        "conta_a_partir_de": "dia em que o defeito ficou evidente",
    },
    "conserto_pelo_fornecedor": {
        "dias": 30,
        "base_legal": "CDC, art. 18, § 1º",
        "quando_usar": "saber até quando a loja ou o fabricante pode consertar o produto; depois disso o consumidor escolhe troca, dinheiro de volta ou abatimento",
        "conta_a_partir_de": "dia em que o produto foi entregue para conserto (reclamação do vício)",
    },
    "reparacao_de_danos": {
        "anos": 5,
        "base_legal": "CDC, art. 27",
        "quando_usar": "pedir indenização por acidente ou dano causado por produto ou serviço defeituoso (fato do produto)",
        "conta_a_partir_de": "conhecimento do dano e de quem o causou",
    },
}

MULTA_MORA_MAXIMA = 0.02


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} deve estar no formato AAAA-MM-DD, recebido: {value!r}") from None


def _add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


def calcular_prazo(tipo: str, data_inicio: str, data_referencia: str | None = None) -> dict:
    if tipo not in PRAZOS:
        raise ValueError(f"tipo inválido: {tipo!r}. Use um de: {', '.join(PRAZOS)}")
    rule = PRAZOS[tipo]
    start = _parse_date(data_inicio, "data_inicio")
    today = _parse_date(data_referencia, "data_referencia") if data_referencia else date.today()
    if start > today:
        raise ValueError("data_inicio não pode ser posterior à data_referencia")
    deadline = _add_years(start, rule["anos"]) if "anos" in rule else start + timedelta(days=rule["dias"])
    remaining = (deadline - today).days
    duration = f"{rule['anos']} anos" if "anos" in rule else f"{rule['dias']} dias"
    return {
        "tipo": tipo,
        "prazo": duration,
        "conta_a_partir_de": rule["conta_a_partir_de"],
        "data_inicio": start.isoformat(),
        "data_limite": deadline.isoformat(),
        "data_referencia": today.isoformat(),
        "dias_restantes": max(remaining, 0),
        "dentro_do_prazo": remaining >= 0,
        "base_legal": rule["base_legal"],
    }


def calcular_repeticao_indebito(valor_pago: float, valor_devido: float) -> dict:
    if valor_pago < 0 or valor_devido < 0:
        raise ValueError("os valores não podem ser negativos")
    if valor_pago <= valor_devido:
        raise ValueError("não há pagamento em excesso: valor_pago deve ser maior que valor_devido")
    excess = round(valor_pago - valor_devido, 2)
    return {
        "valor_pago": round(valor_pago, 2),
        "valor_devido": round(valor_devido, 2),
        "pago_em_excesso": excess,
        "devolucao_em_dobro": round(2 * excess, 2),
        "observacao": "acrescida de correção monetária e juros legais, salvo engano justificável do fornecedor",
        "base_legal": "CDC, art. 42, parágrafo único",
    }


def verificar_multa_atraso(valor_prestacao: float, multa_cobrada: float) -> dict:
    if valor_prestacao <= 0:
        raise ValueError("valor_prestacao deve ser maior que zero")
    if multa_cobrada < 0:
        raise ValueError("multa_cobrada não pode ser negativa")
    limit = round(valor_prestacao * MULTA_MORA_MAXIMA, 2)
    return {
        "valor_prestacao": round(valor_prestacao, 2),
        "multa_cobrada": round(multa_cobrada, 2),
        "multa_maxima_permitida": limit,
        "percentual_cobrado": round(100 * multa_cobrada / valor_prestacao, 2),
        "abusiva": multa_cobrada > limit,
        "excesso": round(max(multa_cobrada - limit, 0), 2),
        "base_legal": "CDC, art. 52, § 1º",
    }
