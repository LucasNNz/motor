# DIREÇÃO V0.12.5 — NÃO FAZER O ENGINE PENSAR

A busca resiliente deve continuar dirigida pela IA externa.

O Engine não deve traduzir, criar sinônimos ou decidir sozinho como ampliar uma pesquisa. A IA que prepara o TXT fornece a consulta principal e, quando necessário, consultas alternativas.

Exemplo:

```txt
query=fork cutlery
fallback_queries=table fork|dinner fork|fork
```

O Engine apenas executa a sequência, mede os resultados e para quando obtém material suficiente.

Para o próximo teste do MVP, usar `GUIA_MVP_PRODUCAO_EXEMPLO_V0125.txt` para evitar repetir o guia V0.12.1 excessivamente restritivo.
