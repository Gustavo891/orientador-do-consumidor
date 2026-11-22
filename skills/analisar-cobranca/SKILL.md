---
name: analisar-cobranca
description: Analisa uma cobrança contestada pelo consumidor (valor cobrado a mais, conta paga em duplicidade, multa de atraso alta em parcela ou financiamento), calcula quanto ele pode exigir de volta ou o valor correto e redige a mensagem de contestação. Use quando o usuário disser que foi cobrado indevidamente, pagou a mais, ou achou a multa por atraso abusiva.
---

# Analisar cobrança

Objetivo: dizer se a cobrança é irregular, quanto o consumidor pode exigir e entregar um texto pronto para contestar. Nunca faça as contas de cabeça: use as ferramentas.

## Passos

1. **Classifique o caso.**
   - *Cobrança indevida já paga* (cobrou a mais, cobrou duas vezes, cobrou algo não contratado e o consumidor pagou): vá ao passo 2.
   - *Multa por atraso* em prestação, parcela ou financiamento: vá ao passo 3.
   - *Cobrança indevida ainda não paga*: não há devolução em dobro, porque ela exige pagamento; oriente a contestar antes de pagar e vá ao passo 4.
   Se faltar um valor necessário (quanto pagou, quanto era devido, valor da parcela ou da multa), **pergunte ao usuário** antes de calcular.

2. **Devolução em dobro:** chame `cdc_calcular_repeticao_indebito(valor_pago, valor_devido)`. Se a ferramenta disser que não há excesso, explique que não cabe devolução.

3. **Multa de atraso:** chame `cdc_verificar_multa_atraso(valor_prestacao, multa_cobrada)`. Juros de mora não entram nesse limite; se o usuário só informou o total pago com atraso, peça o valor da multa separado.

4. **Base legal:** chame `cdc_ler_artigo` com o artigo do caso (`42` para cobrança indevida, `52` para multa) e, se o consumidor foi exposto a constrangimento ou ameaça na cobrança, também o caput do `42`. Se a ferramenta falhar, use a `base_legal` devolvida pelo cálculo.

## Formato da resposta

**Diagnóstico:** uma frase dizendo se a cobrança é irregular e por quê.

| Item | Valor |
|---|---|
| (linhas com os valores devolvidos pela ferramenta, em R$ com duas casas e vírgula decimal) |

**Base legal:** citação curta do artigo entre aspas, com a fonte (CDC, art. X).

**Mensagem para enviar à empresa:**
> Texto de 4 a 6 frases, em primeira pessoa, identificando a cobrança, citando o artigo, pedindo o valor calculado (ou o cancelamento da cobrança) e um prazo de 10 dias para resposta, informando que, sem solução, a reclamação será registrada no Procon ou no consumidor.gov.br.
