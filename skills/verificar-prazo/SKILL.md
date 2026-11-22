---
name: verificar-prazo
description: Verifica se o consumidor ainda está no prazo para desistir de uma compra, reclamar de um defeito ou exigir o conserto, a partir da data da compra ou do recebimento. Use quando o usuário perguntar "ainda dá tempo de devolver/trocar/reclamar?", "meu prazo já venceu?" ou contar quando comprou ou recebeu um produto com problema.
---

# Verificar prazo do consumidor

Objetivo: dizer, com data, se o prazo do consumidor ainda está aberto, qual é a base legal e o que fazer em seguida. Nunca calcule datas de cabeça: use as ferramentas.

## Passos

1. **Reúna os fatos do pedido.** Identifique:
   - onde foi a compra: fora da loja física (internet, aplicativo, telefone, em casa) ou na loja física;
   - se há defeito; se há, se ele é aparente (visível ao receber) ou oculto (apareceu com o uso);
   - se o produto é durável (eletrônico, eletrodoméstico, móvel, roupa) ou não durável (alimento, cosmético, serviço pontual);
   - a data de início: recebimento do produto, para arrependimento e vício aparente; dia em que o defeito apareceu, para vício oculto; dia em que foi entregue para conserto, para o prazo do fornecedor.
   Se a data de início não foi informada, **pare e pergunte** a data ao usuário. Não suponha datas.

2. **Descubra a data de hoje** com `time_get_current_time`, timezone `America/Sao_Paulo`. Use só a parte AAAA-MM-DD do campo `datetime`.

3. **Escolha o tipo de prazo** para `cdc_calcular_prazo`:
   - compra fora da loja, sem defeito ou com defeito: `arrependimento` (7 dias);
   - defeito aparente: `vicio_aparente_duravel` (90 dias) ou `vicio_aparente_nao_duravel` (30 dias);
   - defeito oculto: `vicio_oculto_duravel` ou `vicio_oculto_nao_duravel`;
   - produto na assistência há muito tempo: `conserto_pelo_fornecedor` (30 dias);
   - compra na loja física **sem** defeito: não existe prazo legal de troca; diga que a troca depende da política da loja e não chame a ferramenta.
   Se a compra foi online **e** tem defeito, calcule os dois prazos (arrependimento e vício) e mostre os dois.

4. **Calcule** com `cdc_calcular_prazo(tipo, data_inicio, data_referencia=<hoje>)`, sempre com a data de hoje obtida no passo 2. Se a ferramenta devolver erro de formato, corrija a data para AAAA-MM-DD e tente uma vez mais.

5. **Busque o texto da lei** com `cdc_ler_artigo` usando o número do artigo da `base_legal` devolvida (por exemplo `49` ou `26`). Se a compra foi pela internet e o tipo é arrependimento, leia também o artigo `5` com `lei="decreto_7962"`, que diz como exercer o direito online.

6. Se `time_get_current_time` falhar, peça ao usuário a data de hoje. Se `cdc_ler_artigo` falhar, responda mesmo assim citando a `base_legal` do cálculo.

## Formato da resposta

Responda exatamente nesta estrutura, em português, uma seção por prazo calculado:

**Situação:** uma frase resumindo o caso.
**Prazo aplicável:** <duração> — <base_legal>
**Conta a partir de:** <data_inicio em DD/MM/AAAA> (<conta_a_partir_de>)
**Data-limite:** <data_limite em DD/MM/AAAA> — **DENTRO DO PRAZO** (<dias_restantes> dias restantes) ou **PRAZO ENCERRADO**
**O que diz a lei:** citação curta, entre aspas, do trecho que fundamenta o prazo.
**Próximo passo:** o que o consumidor deve fazer agora (por exemplo, registrar o pedido por escrito pelo mesmo canal da compra e guardar o protocolo; se encerrado, se ainda cabe vício oculto ou reparação de danos).
