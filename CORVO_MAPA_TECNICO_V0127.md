# CORVO IMAGE ENGINE V0.12.7 — GEOMETRIA GUIADA DO OBJETO

## Problema isolado no teste V0.12.6
A busca externa e o recorte passaram, mas o objeto ficou pequeno, inclinado e deslocado. O fundo demo também apareceu apesar de o guia pedir fundo simples.

## Correções
- `subject_scale` agora atua sobre o eixo principal do sujeito em cenas de objeto único.
- Em saída vertical, `subject_scale=62%` pode ocupar ~62% da altura útil, em vez de 62% do lado menor do canvas.
- `orientation=vertical|horizontal` é executado geometricamente.
- O Engine estima o eixo principal da máscara do objeto e aplica rotação determinística para alinhar à orientação pedida.
- `subject_x` / `subject_y` centralizam o objeto recortado real.
- fundo uniforme é criado a partir de `[BACKGROUND]` quando não existe `SEARCH_BACKGROUND`.
- `bg_plain_light` demo não é mais injetado silenciosamente em execução guiada sem busca de fundo.
- a interface sincroniza o seletor de formato com `[OUTPUT] width/height/aspect_ratio` do TXT.
- logs do Composer registram `orientation_requested`, `rotation_applied_deg`, `subject_scale` e `subject_box_px`.

## Limite consciente do MVP
Rotação geométrica corrige a orientação 2D do recorte, mas não transforma uma foto 3/4 em vista frontal verdadeira. Isso continua sendo responsabilidade futura do refinador visual generativo. O MVP não deve fingir que consegue fazer essa transformação sem um modelo adequado.
