# CORREÇÃO DO CONTRATO COMPOSTO — V0.12.16

## Caso de regressão

Entrada antiga:

```text
query=fork isolated front view
fallback_queries=silver fork front view|table fork front view|fork top view
```

Sequência efetiva nova:

```text
fork cutlery illustration
fork cutlery vector
fork cutlery icon
fork cutlery
table fork utensil
fork isolated front view
silver fork front view
table fork front view
fork top view
```

O Engine para na primeira query que salvar uma referência utilizável. Não há fallback silencioso para asset demo.

## Validação de deploy

Depois de publicar, abra `/api/health` e confirme:

```text
version=0.12.16
X-Corvo-Build=0.12.16-composite-contract
```
