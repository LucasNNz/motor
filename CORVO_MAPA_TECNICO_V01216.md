# CORVO IMAGE ENGINE V0.12.16 — CONTRATO COMPOSTO EXECUTÁVEL

## Problema observado
A busca real trouxe 17 referências, mas todas foram rejeitadas pelo filtro `isolated=true`. Além disso, o log provou que um guia antigo ainda podia enviar apenas buscas fotográficas: `fork isolated front view`, `silver fork front view`, `table fork front view` e `fork top view`.

## Correções preservadas
`isolated=true` passa a aceitar três caminhos auditáveis:
1. `transparent` — referência já possui alpha;
2. `isolated` — referência atinge o limiar visual estrito;
3. `cutout` — o fundo não é perfeito, mas é removível deterministicamente pelo Composer.

## Novos sinais
- `cutout_score`
- `cutout_compatible`
- `foreground_ratio`
- `border_foreground_ratio`
- `acceptance_mode`

## Composer
A remoção de fundo agora aceita também fundo claro de estúdio com pequena variação, usando estatística da borda. Fundo escuro/texturizado continua preservado/rejeitado.

## Recuperação preservada da V0.12.13
Quando um `[SEARCH_OBJECT]` antigo não possui nenhuma rota limpa, o Engine acrescenta automaticamente, antes das tentativas antigas:

1. `<objeto> front view icon`;
2. `<objeto> cutlery/object front view icon`;
3. `<objeto> illustration front view`;
4. `<objeto> vector front view`;
5. `<objeto> transparent png`.

As queries originais continuam como fallback e permanecem visíveis no diagnóstico. Se o guia já define icon/illustration/vector/transparent/PNG, ele é respeitado sem duplicar a recuperação.

## Correção da V0.12.14

O caso real selecionou `Asbestopluma ramuscula sp. nov.` para o conceito `garfo`. A referência passou porque a busca associou `fork` a outro sentido e porque um alpha parcial recebeu nota máxima.

Agora o candidato precisa provar semanticamente que contém o objeto. Também só recebe `transparent=true` quando possui pixels realmente transparentes, área útil coerente e borda majoritariamente livre.

## Execução visual preservada

O modelo browser atual melhora resolução, mas não realiza style transfer generativo. Por isso, quando o guia pede `2d_semirealistic`, o Composer executa uma transformação determinística antes do refinador: suavização, paleta controlada, preservação parcial de material e contornos limpos.

## Guia composto

O parser entende tanto `SEARCH_CHARACTER`/`SEARCH_BACKGROUND` quanto `SUBJECT_SEARCH`/`BACKGROUND_SEARCH`. Listas multilinha de queries são preservadas e executadas em ordem. Personagem e fundo são obrigatórios no task `character_in_environment`.
