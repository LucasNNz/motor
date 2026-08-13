# CORVO IMAGE ENGINE V0.12.10 — CONTRATO DE GUIA ESTRITO

## Diagnóstico da operação real
A operação `1786641540_b63696` provou que busca, referência fixada, 9:16 e exportação browser estavam funcionando, mas o guia não declarou orientação nem vista desejada.

Log real:
- `orientation_requested = null`
- `rotation_applied_deg = 0`
- `subject_scale = 0.62`
- `subject_box_px = [137, 508, 446, 264]`

Por isso o Composer preservou o garfo diagonal e aplicou 62% no eixo não orientado.

## Correção
Para `task=single_object_quiz`, o guia passa por validação antes da coleta. O Engine exige decisões explícitas, sem inferir intenção:
- `orientation=vertical|horizontal|free`
- `desired_view=front|side|3/4|free`
- `subject_x`, `subject_y`, `subject_scale`
- SEARCH_OBJECT com query
- OUTPUT explícito
- RENDER presente

O endpoint `/api/guide/parse` agora retorna `contract.valid`, `contract.issues` e `contract.warnings`.

A tela informa `contrato OK` ou lista o que falta assim que o TXT é carregado.

## Teste com a referência real da operação
Com a mesma referência `obj_garfo_0005` e `orientation=vertical`:
- rotação aplicada: `-61.48°`
- eixo final: `90.04°`
- caixa final prevista: `328 × 793 px`
- saída: `720 × 1280`

## Filosofia preservada
A IA externa decide. O Corvo valida e executa. Se uma decisão visual necessária não vier no guia, o Engine não inventa e não desperdiça uma geração inteira.
