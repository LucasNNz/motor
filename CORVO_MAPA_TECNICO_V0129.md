# CORVO IMAGE ENGINE V0.12.9 — EXPORTAÇÃO DE OPERAÇÃO NO NAVEGADOR

## Problema corrigido
No Vercel, `operations/` fica em `/tmp`. A geração e o clique em `Exportar operação` são requisições diferentes e podem cair em instâncias diferentes. Por isso o endpoint antigo podia responder `Operação não encontrada`.

## Nova arquitetura do export
A operação de produção não depende mais de uma segunda Function para montar o ZIP.

Fluxo:

GUIA → BUSCA → REFERÊNCIAS → COMPOSIÇÃO → resposta da mesma Function já leva composição + logs + bytes das referências → REFINO NO BROWSER → BROWSER MONTA O ZIP.

## Conteúdo do ZIP browser
- pedido_original.txt
- guia_auxiliar.txt
- resultado_final.png
- etapas/composicao_base.png
- etapas/antes_refinamento.png
- etapas/depois_refinamento.png
- referencias_usadas/*
- logs/buscas.json
- logs/referencias.json
- logs/composicao.json
- logs/refinador.json
- logs/condicionamento.json
- logs/tempos.json
- logs/execucao.json
- logs/erros.json
- logs/avaliacao.json
- logs/operacao.json
- diagnostico.txt

## Mudança importante
O `resultado_final.png` do ZIP é o resultado refinado no navegador, exatamente o que o usuário vê e baixa.

O endpoint legado `/api/operations/{id}/export` permanece apenas para uso local/diagnóstico. O fluxo principal `Criar` não depende mais dele.
