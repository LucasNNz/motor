# Corvo Image Engine V0.12 — MVP de Produção Guiada

A entrada principal agora é **PROMPT + GUIA TXT**. O Engine não tenta substituir a IA que planejou a imagem: ele executa as instruções do guia.

## Fluxo principal

PROMPT + GUIA TXT → buscas dirigidas → filtros → biblioteca auditável → seleção → composição → refinador browser → PNG → operação exportável.

## Uso rápido

1. Abra o app.
2. Em **Criar**, informe o prompt.
3. Carregue o TXT guia da imagem.
4. Escolha o formato.
5. Clique **Gerar imagem**.
6. Baixe o PNG; se quiser auditoria, use **Exportar operação**.

## Guia

O parser entende, entre outros: `[SCENE]`, `[SEARCH_CHARACTER]`, `[SEARCH_POSE]`, `[SEARCH_BACKGROUND]`, `[SEARCH_OBJECT]`, `[SEARCH_LIGHTING]`, `[FILTER]`, `[COMPOSITION]`, `[RENDER]`, `[REPROCESS]` e `[FIX]`.

Cada bloco `SEARCH_*` pode informar `provider=` ou `providers=`. Exemplos atuais: `openverse` e `wikimedia_commons`.

## fast_mvp

No fluxo principal o sistema usa uma política rápida de coleta para provar produção sem esperar centenas de downloads por componente. O pedido original e os limites efetivamente usados ficam registrados no histórico da busca.

## Biblioteca

Referências novas ficam como `candidates` por padrão. No modo de produção guiada elas podem ser usadas imediatamente naquela operação sem serem promovidas permanentemente a `approved`.

## Refinador

O refinador principal continua rodando no navegador. A V0.12 passa as diretivas do `[RENDER]` para o runtime browser e registra instruções que o modelo atual ainda não consegue cumprir generativamente (por exemplo anatomia/redesenho).

O modelo browser atual ainda é o gargalo para redesenho generativo forte; o restante do pipeline já está organizado para trocar esse provider sem refazer a arquitetura.
