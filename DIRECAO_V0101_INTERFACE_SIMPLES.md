# CORVO IMAGE ENGINE V0.10.1 — INTERFACE SIMPLES

## Regra de produto
A tela principal não deve expor decisões técnicas que o sistema pode tomar sozinho.

Fluxo principal:

**CRIAR → LOTE → BIBLIOTECA → AVANÇADO**

### Criar
- prompt
- formato 1:1 / 16:9 / 9:16
- Gerar imagem
- preview
- Baixar PNG

O refinador browser é preparado automaticamente quando necessário.

### Lote
- importar TXT ou colar prompts
- escolher formato do lote
- Gerar lote
- acompanhar progresso
- Baixar ZIP

### Biblioteca
- busca
- filtros simples
- galeria
- coleta manual fica recolhida em “Adicionar referências”

### Avançado
Somente para desenvolvimento/diagnóstico:
- Composer
- WebGPU/WASM
- cache e modelo
- benchmark
- execução guiada
- reprocessamento
- backend legado
- arquitetura

## Princípio
O usuário não precisa saber se a execução usou WebGPU ou WASM para criar uma imagem. O sistema escolhe e só apresenta erro quando houver algo que realmente exija ação.
