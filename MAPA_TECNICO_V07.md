# MAPA TÉCNICO — CORVO IMAGE ENGINE V0.7

## Entrada / API

`engine/server.py`
- FastAPI e interface local.
- geração antiga por prompt;
- lote por TXT;
- coleta manual;
- biblioteca;
- benchmark do refinador;
- novo caminho por guia;
- avaliação e exportação de operação.

`engine/models.py`
- contratos Pydantic dos endpoints.

## Guia técnico

`engine/guide_parser.py`
- parser INI-like para `[SCENE]`, `[SEARCH_*]`, `[FILTER]`, `[COMPOSITION]`, `[RENDER]`, `[REPROCESS]` e `[FIX]`;
- preserva múltiplos blocos da mesma seção;
- converte booleanos, números, porcentagens e listas.

`engine/guided_service.py`
- transforma o guia em ações do Engine;
- cria buscas por componente;
- aceita o formato compacto `[SEARCH]` e completa buscas mínimas a partir de `[SCENE]`;
- chama coleta quando solicitado;
- chama Composer guiado;
- chama refinador opcional;
- registra referências e tempos;
- cria operação auditável.

## Busca / coleta

`engine/providers/openverse.py`
`engine/providers/wikimedia.py`
- fontes de coleta atuais.

`engine/collector_service.py`
- executa query por componente;
- baixa candidatos;
- aplica filtro/ranking;
- grava referências na biblioteca;
- registra histórico da busca.

`engine/filter_pipeline.py`
- resolução mínima;
- quality score;
- relevance score;
- deduplicação/quase duplicação por hash perceptual;
- thresholds configuráveis;
- heurística de metadados para texto/logo/marca-d'água.

## Biblioteca visual

`engine/memory_manager.py`
- raiz nova: `CORVO_LIBRARY/`;
- estados físicos `candidates / approved / rejected`;
- sidecar JSON por imagem;
- `search_history.json` por conceito;
- tags, mover categoria, apagar;
- preferred / blocked;
- used_count / operations_used;
- approved_results / rejected_results / success_rate;
- ranking usa qualidade, relevância, aprovação, preferência e histórico;
- migração do antigo `visual_memory/` quando houver dados.

`visual_bank/`
- banco demo original; continua como fallback/regressão.
- não substitui a `CORVO_LIBRARY` como memória coletada auditável.

## Composição

`engine/composer_engine.py`
- mantém `PromptInterpreter` para compatibilidade V0.6;
- novo `plan_from_guide()` não depende do prompt natural;
- novo `generate_guided()` executa seleção estruturada;
- usa apenas referências aprovadas da `CORVO_LIBRARY` no caminho automático;
- fallback demo continua disponível quando a biblioteca ainda não possui o componente.

## Refinamento

`engine/refiner.py`
- `light_cpu`: baseline não generativo;
- `sdcpp_img2img`: img2img via stable-diffusion.cpp.

`engine/refiner_benchmark.py`
- benchmark V0.6 preservado.

`engine/sdcpp_manager.py`
- gerencia instalação/processo do `sd-server`.

### Limitação atual do refinador

Na V0.7 as referências são resolvidas, usadas para montar a composição-base e exportadas/logadas. O backend SD.CPP atual ainda recebe diretamente a composição-base + prompt técnico de preservação; condicionamento simultâneo por várias imagens de referência (ex.: IP-Adapter/ControlNet específico) ainda não foi ligado porque depende do backend/modelos auxiliares.

## Operações e logs

`engine/operation_manager.py`
- cria `operations/operacao_*`;
- pedido + guia;
- resultado final;
- etapas antes/depois;
- cópias das referências usadas;
- JSONs de busca, referência, composição, refinador, tempos, erros e avaliação;
- diagnóstico;
- exportação ZIP reconstruível.

No lote antigo, cada PNG agora também ganha `operation_id` e `export_url`.

## Interface

`engine/static/index.html`
`engine/static/app.js`
`engine/static/styles.css`
- painel novo “Execução Guiada por TXT”;
- executar buscas do guia;
- executar composição/refino;
- aprovar/reprovar geração;
- anotar erro;
- exportar operação;
- biblioteca com filtro por estado;
- aprovar/reprovar referência;
- preferred / blocked;
- editar tags;
- mover categoria;
- apagar.

## Pontos ainda experimentais

1. Detecção de texto/logo/marca-d'água é heurística por metadados; não usa OCR pesado.
2. Classificação semântica profunda, embeddings e detector de esqueleto ainda não foram adicionados.
3. Iluminação/câmera podem ser coletadas e auditadas, mas o Composer clássico ainda usa apenas uma harmonização determinística simples para temperatura de luz.
4. Reprocessamento `[REPROCESS]/[FIX]` já é parseado, mas a edição regional/máscara ainda precisa ser ligada a um backend capaz de inpainting/masking.
5. O benchmark do refinador continua separado da execução guiada para permitir comparação limpa de desempenho.
