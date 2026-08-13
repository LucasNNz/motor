# CORVO IMAGE ENGINE V0.12.4 — STORAGE /TMP SEGURO

## Correção principal
A V0.12.3 conseguiu avançar até a gravação da referência, mas uma execução Vercel falhou ao salvar em uma pasta temática dentro de `/tmp`.

A V0.12.4 corrige a camada de armazenamento:

- toda gravação de imagem recria `category/concept/status` imediatamente antes de salvar;
- `reload()` recria a estrutura base se necessário;
- entradas de índice cujo arquivo físico não existe são removidas do índice ativo;
- `save()` recria a pasta do índice antes da escrita;
- `search_history.json` recria sua pasta antes de salvar;
- o pacote de produção foi limpo e não contém referências artificiais usadas nos testes de regressão.

## Regra MVP
O Engine nunca deve depender de uma pasta dinâmica já existir em `/tmp`. Cada escrita deve ser autossuficiente.

## Validação executada
Foi simulada a remoção completa de `CORVO_LIBRARY` depois da inicialização do `MemoryManager`. A próxima chamada `add_item_from_image()` recriou automaticamente:

`/tmp/.../CORVO_LIBRARY/OBJECTS/garfo_v123/candidates/`

e salvou o PNG corretamente.
