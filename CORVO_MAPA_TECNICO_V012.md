# CORVO IMAGE ENGINE V0.12 — MVP DE PRODUÇÃO GUIADA

## Decisão de arquitetura
O Engine não deve tentar pensar como um LLM. A IA externa entrega PROMPT + GUIA; o Corvo executa.

## Fluxo implementado
1. entrada principal: prompt + arquivo TXT guia;
2. parser identifica SEARCH_*, FILTER, COMPOSITION e RENDER;
3. cada SEARCH_* pode escolher provider/API;
4. modo `fast_mvp` limita a amostra de coleta para reduzir latência, registrando solicitado x efetivo;
5. referências novas permanecem `candidates`, mas podem ser usadas na operação atual;
6. Composer seleciona usando o guia e pode usar candidates da sessão;
7. objeto central obedece `subject_x`, `subject_y`, `subject_scale` e `shadow`;
8. imagens de objeto com fundo de borda uniforme recebem cutout heurístico leve antes da composição;
9. refinador browser recebe diretivas do guia e registra diretivas ainda não suportadas pelo modelo atual;
10. resultado refinado no navegador é sincronizado de volta à operação;
11. Exportar operação inclui o PNG final visto pelo usuário e os logs.

## Providers atuais
- Openverse
- Wikimedia Commons

## O que continua experimental
- redesenho generativo forte;
- anatomia/encaixes por modelo generativo;
- identidade e pose como condicionamento visual browser real;
- segmentação robusta de pessoas/objetos complexos.

## Gargalo atual real
O Engine/guia/busca/biblioteca/composição/logs já têm um caminho de produção. O maior gargalo restante é trocar o enhancer browser atual por um provider generativo browser capaz de executar `redraw_connections`, `fix_anatomy`, identidade e pose.
