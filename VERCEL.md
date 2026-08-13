# Corvo Image Engine V0.12 — Vercel

O Vercel distribui a interface e executa as funções leves de busca/composição/logs. O refinamento de IA ocorre no navegador via WebGPU/WASM.

A biblioteca e operações no runtime Vercel usam armazenamento temporário da instância; para persistência entre instâncias, a próxima integração deve usar storage externo. O MVP atual mantém exportação de operação para não perder o histórico da geração.

O caminho de produção é PROMPT + GUIA TXT. SD.CPP/Diffusers permanecem somente como legado opcional local.
