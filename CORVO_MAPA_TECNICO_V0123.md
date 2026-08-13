# CORVO IMAGE ENGINE V0.12.3 — MVP ANTI-TIMEOUT

## Problema corrigido
A V0.12.2 ainda permitia chamadas externas e downloads demorados demais para uma Vercel Function configurada com `maxDuration=60`.

## Mudanças
- API Openverse/Wikimedia: timeout de conexão/leitura curto;
- downloads: timeout curto e sem retry automático demorado;
- no `fast_mvp`, cada SEARCH coleta no máximo 6 resultados e busca apenas 2 referências úteis;
- a coleta para assim que o `keep_limit` efetivo é satisfeito;
- no modo rápido, no máximo 2 URLs são tentados por referência;
- cada bloco tem orçamento de processamento e o guia inteiro tem orçamento global;
- fallback opcional do mesmo componente é pulado quando a busca principal já entregou referência;
- referências abaixo de `min_resolution` podem ser rejeitadas pelos metadados antes do download;
- diagnóstico registra `candidates_processed`, `budget_exhausted` e `processing_ms`;
- erro 504 na interface recebe mensagem específica.

## Regra do MVP
O Engine não deve esperar indefinidamente por uma fonte externa. Referência lenta é tratada como referência indisponível naquele momento. O guia continua mandando o que buscar; o executor controla apenas o orçamento operacional.

## Configuração Vercel
Mantemos `maxDuration=60`. O objetivo não é esconder operações lentas aumentando o timeout, e sim manter a etapa servidor dentro de uma janela previsível. O refino continua no navegador.
