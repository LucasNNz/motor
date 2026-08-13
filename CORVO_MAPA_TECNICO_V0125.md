# CORVO IMAGE ENGINE V0.12.5 — BUSCA GUIADA COM FALLBACKS

## Problema isolado
A execução V0.12.4 chegou ao coletor, mas uma query Openverse muito restritiva retornou 0 resultados em poucos milissegundos. Como nenhum candidato foi processado, não era problema de download, filtro, storage ou refinador.

## Correção MVP
O guia pode agora definir uma sequência explícita de consultas:

```txt
[SEARCH_OBJECT]
provider=openverse
query=fork cutlery
fallback_queries=table fork|dinner fork|fork
```

O Engine:
1. executa `query`;
2. se não salvar referência utilizável, executa cada `fallback_queries` na ordem;
3. para na primeira consulta que produzir material utilizável;
4. não inventa tradução, sinônimo ou nova consulta;
5. registra todas as tentativas e resultados.

Também são aceitos:

```txt
query_fallback_1=table fork
query_fallback_2=fork
```

## Diagnóstico
Cada operação passa a registrar por tentativa:
- query;
- resultados encontrados;
- candidatos processados;
- candidatos aceitos;
- candidatos salvos;
- erros do provider;
- tempo.

O provider também registra `provider_trace` com status, quantidade e tempo de cada chamada.

## Interface
Ao carregar um guia com `SEARCH_*` sem fallback, a interface exibe um aviso curto. Isso não bloqueia a execução.

## Escopo
Nenhuma mudança no Composer ou no refinador nesta versão.
