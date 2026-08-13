# Diagnóstico — operação_1786630568_b8f007

## O que aconteceu
- O guia solicitou busca de um garfo frontal e isolado.
- A busca retornou `candidates_found=0`.
- Wikimedia Commons retornou HTTP 403.
- Nenhuma referência entrou na `CORVO_LIBRARY`.
- O Composer então utilizou `obj_fork` e `bg_plain_light` do `demo_bank`.
- O refinador browser executou `model+enhance`, mas apenas poliu a montagem demo.
- O guia pediu `aspect_ratio=9:16`, porém a operação foi gerada em 768×768.

## Correções V0.12.1
1. SEARCH_* explícito é obrigatório por padrão.
2. Sem referência utilizável, o Engine para e informa a busca que falhou.
3. `required=false` ou `fallback=demo` permite fallback de forma explícita.
4. Wikimedia recebe User-Agent identificador.
5. Provider recebe filtros do próprio bloco de guia (license_type, category, aspect_ratio etc.).
6. `[OUTPUT]` passa a controlar largura/altura/aspect ratio da execução guiada.
7. `subject_scale=large` passa a ter significado determinístico no Composer.
8. `[LIGHTING]` simples passa a afetar a composição determinística.

## Conclusão
O gargalo dessa operação ocorreu antes do refinador: a busca externa não forneceu referência e o fallback demo mascarou a falha.
