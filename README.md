# Corvo Image Engine V0.12.13 — MVP de Produção Guiada

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

O refinador principal continua rodando no navegador. A V0.12.1 passa as diretivas do `[RENDER]` para o runtime browser e registra instruções que o modelo atual ainda não consegue cumprir generativamente (por exemplo anatomia/redesenho).

O modelo browser atual ainda é o gargalo para redesenho generativo forte; o restante do pipeline já está organizado para trocar esse provider sem refazer a arquitetura.

## V0.12.1 — correções após operação real

- `SEARCH_*` explícito é obrigatório por padrão; falha de busca não é mais mascarada por demo asset.
- Use `required=false` ou `fallback=demo` quando o guia quiser permitir fallback.
- Wikimedia Commons agora recebe cabeçalho identificador de cliente.
- Filtros de provider podem vir do próprio bloco `SEARCH_*`.
- `[OUTPUT] width`, `height`, `size` e `aspect_ratio` passam a controlar a resolução guiada.
- Valores semânticos de composição como `subject_scale=large` agora são resolvidos deterministicamente.
- `[LIGHTING]` simples é aplicado pelo Composer quando não há uma referência visual de iluminação.

## V0.12.9 — exportação browser-first
No fluxo principal de produção, `Exportar operação` é montado no navegador. Isso evita depender de `/tmp` entre requisições Vercel e garante que o ZIP contenha o PNG refinado final visto pelo usuário.


## V0.12.11 — filtro recortável para o MVP

- `isolated=true` aceita referência transparente, realmente isolada ou `cutout_compatible`;
- registra `isolation_score`, `cutout_score`, `cutout_compatible` e `acceptance_mode`;
- fundos claros de estúdio com pequena variação podem ser removidos deterministicamente pelo Composer;
- fundos escuros/texturizados continuam rejeitados quando o guia pede fundo claro e baixo ruído;
- o guia de teste procura primeiro ilustração/PNG e usa foto recortável apenas como fallback.

## V0.12.13 — recuperação de guia antigo

- se um `SEARCH_OBJECT` não traz rota de ícone, ilustração, vetor, transparência ou PNG, o Engine cria essa rota automaticamente;
- as buscas limpas são tentadas antes das queries fotográficas antigas;
- as queries originais continuam disponíveis como fallback e aparecem no log;
- o build pode ser confirmado por `/api/health`: `version=0.12.13` e cabeçalho `X-Corvo-Build: 0.12.13-search-recovery`.
