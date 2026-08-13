# CORREÇÃO DA BUSCA — V0.12.14

## Caso de regressão

Entrada antiga:

```text
query=fork isolated front view
fallback_queries=silver fork front view|table fork front view|fork top view
```

Sequência efetiva nova:

```text
fork cutlery
table fork utensil
dining fork silverware
fork cutlery illustration
fork utensil isolated
fork isolated front view
silver fork front view
table fork front view
fork top view
```

O Engine para na primeira query que salvar uma referência utilizável. Não há fallback silencioso para asset demo.

## Validação de deploy

Depois de publicar, abra `/api/health` e confirme:

```text
version=0.12.14
X-Corvo-Build=0.12.14-semantic-guard
```
