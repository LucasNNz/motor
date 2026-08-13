# CORVO IMAGE ENGINE V0.12.8 — REFERÊNCIA FIXADA + GEOMETRIA REAL

## Problemas observados na V0.12.7
- o formato e o fundo estavam corretos, mas o objeto ainda podia aparecer pequeno e inclinado;
- a composição podia voltar à biblioteca global depois da coleta e selecionar uma referência antiga da instância `/tmp`;
- halos de alpha quase invisíveis podiam manter a caixa do recorte grande, reduzindo o objeto real.

## Correções
1. A referência coletada/selecionada na operação é fixada por ID antes do Composer.
2. O primeiro SEARCH_* do componente tem prioridade; blocos seguintes são fallback.
3. Duplicata encontrada durante a coleta reutiliza exatamente o item duplicado, em vez de fazer novo ranking global.
4. O refinador recebe a mesma referência que o Composer efetivamente utilizou.
5. Crop de foreground ignora alpha fraco/halo e calcula a caixa com foreground forte.
6. `orientation=vertical` usa o eixo principal do foreground recortado.
7. `subject_scale` é aplicado depois de recorte e rotação, ao objeto real.
8. O log inclui source_subject_px, oriented_subject_px, rotation_applied_deg e subject_box_px.

## Critério do MVP
Para o guia do garfo, o resultado precisa ser: objeto central, vertical, grande, fundo simples e referência da própria operação.
