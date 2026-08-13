# CORVO IMAGE ENGINE V0.12.2 — BUSCA RESILIENTE

## Objetivo desta revisão
Corrigir exclusivamente a etapa que impedia o MVP guiado de chegar ao Composer com uma referência real.

## Correções
- Openverse agora expõe múltiplas rotas de download por referência.
- O coletor tenta primeiro o proxy/thumbnail da própria Openverse, depois thumbnail e URL original.
- Downloads usam retry curto para 429/5xx e validam se o conteúdo recebido é realmente uma imagem.
- O score de qualidade foi recalibrado: uma referência utilizável com lado curto de 512 px não começa matematicamente abaixo de 0.60.
- `license_type` deixou de ser imposto pelo provider; ele só é enviado quando o guia pedir.
- Erros HTTP dos providers agora incluem status e corpo resumido.
- Cada coleta gera `diagnostics`: encontrados, passaram filtro, salvos, erros de provider e principais motivos de rejeição.
- Quando uma busca obrigatória falha, a mensagem final inclui esses diagnósticos.

## Query de teste
O guia de garfo passou de uma query longa com vários termos AND para:

`query=fork cutlery`

Detalhes como posição, fundo, estilo e iluminação continuam nos blocos de composição/render. O Engine não inventa uma nova query.

## Teste local sem internet externa
Foi simulado um provider Openverse devolvendo uma referência 900×1200 com o primeiro URL de download bloqueado e o segundo válido.

Resultado esperado do pipeline:
- candidatos encontrados: 1
- passaram filtro: 1
- candidates salvos: 1
- referência usada pelo Composer: `obj_garfo_0001`
- saída resolvida pelo guia: 720×1280

A execução real contra a Openverse precisa ser confirmada no deployment, porque o ambiente de desenvolvimento usado para empacotar não possui acesso DNS externo.
