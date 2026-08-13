# CORVO IMAGE ENGINE V0.12.13 — RECUPERAÇÃO DE BUSCA DE OBJETOS

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

## Recuperação nova na V0.12.13
Quando um `[SEARCH_OBJECT]` antigo não possui nenhuma rota limpa, o Engine acrescenta automaticamente, antes das tentativas antigas:

1. `<objeto> front view icon`;
2. `<objeto> cutlery/object front view icon`;
3. `<objeto> illustration front view`;
4. `<objeto> vector front view`;
5. `<objeto> transparent png`.

As queries originais continuam como fallback e permanecem visíveis no diagnóstico. Se o guia já define icon/illustration/vector/transparent/PNG, ele é respeitado sem duplicar a recuperação.
