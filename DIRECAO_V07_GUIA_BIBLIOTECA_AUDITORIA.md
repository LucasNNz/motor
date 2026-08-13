# DIREÇÃO V0.7 — GUIA, BIBLIOTECA VISUAL AUDITÁVEL E OPERAÇÕES

A V0.7 mantém o V0.6 para benchmark, mas cria o novo caminho principal experimental:

```text
PEDIDO + GUIA TÉCNICO
→ SEARCH_* DIRIGIDO
→ FILTER CONFIGURÁVEL
→ CORVO_LIBRARY
→ COMPOSER GUIADO
→ REFINADOR OPCIONAL
→ RESULTADO + LOGS + ZIP DA OPERAÇÃO
```

## Compatibilidade

O modo antigo por prompt continua disponível. Ele não é removido porque ainda serve para comparação e regressão.

## Guia técnico

O parser entende seções INI-like, incluindo:

- `[SCENE]`
- `[SEARCH_CHARACTER]`
- `[SEARCH_POSE]`
- `[SEARCH_FACE]`
- `[SEARCH_BACKGROUND]`
- `[SEARCH_OBJECT]`
- `[SEARCH_LIGHTING]`
- `[SEARCH_CAMERA]`
- `[FILTER]`
- `[COMPOSITION]`
- `[RENDER]`
- `[REPROCESS]`
- `[FIX]`

O Engine executa os campos; ele não precisa de LLM local para interpretar linguagem natural nesse caminho.

## Biblioteca física

A nova raiz é:

```text
CORVO_LIBRARY/
```

Cada categoria é organizada por conceito e possui:

```text
candidates/
approved/
rejected/
search_history.json
```

Cada imagem possui sidecar JSON com origem, query, licença, scores, uso, estado, preferência, bloqueio e sucesso histórico.

## Filtros configuráveis

O guia pode definir:

```text
min_resolution
reject_text
reject_logos
reject_watermarks
remove_duplicates
remove_near_duplicates
quality_threshold
similarity_threshold
```

Observação do MVP: rejeição de texto/logo/marca-d'água usa metadados da fonte como heurística. Não há OCR pesado embutido nesta versão.

## Operações

Cada execução guiada cria:

```text
operations/operacao_x/
  pedido_original.txt
  guia_auxiliar.txt
  resultado_final.png
  etapas/
  referencias_usadas/
  logs/
  diagnostico.txt
```

A interface permite aprovar/reprovar o resultado, anotar erro e exportar o ZIP completo da operação.

## Aprendizado auditável

Ao aprovar/reprovar uma operação, as referências da biblioteca utilizadas recebem atualização de:

- `approved_results`
- `rejected_results`
- `success_rate`

O ranking prioriza referências aprovadas, preferidas e com melhor histórico, e exclui referências bloqueadas/rejeitadas.
