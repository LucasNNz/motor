# Direção V0.4 — Composer Engine

## Princípio

O Corvo Image Engine deixa de tratar geração diffusion completa como núcleo obrigatório. O motor principal passa a ser:

**composição + memória visual + refinamento opcional**.

## Restrição estrutural

CUDA não pode ser requisito. A arquitetura deve continuar útil em PCs comuns, usando CPU e, futuramente, acelerações como ONNX Runtime, DirectML ou OpenVINO quando fizer sentido.

## MVP 1

- banco visual manual;
- metadados por asset;
- interpretação simples do prompt;
- seleção de componentes por tags;
- compatibilidade pose/roupa;
- âncoras para rosto e objetos;
- composição em camadas RGBA;
- harmonização leve não generativa;
- geração única e lote por TXT;
- PNG + ZIP.

## Fora do escopo imediato

- scraping/coleta automática;
- treinamento por referência;
- refinamento generativo pesado;
- tentativa de gerador universal.

## Fase seguinte

Substituir gradualmente os assets demo por componentes visuais de maior qualidade e medir quanto a sensação de colagem cai antes de investir em refinamento de IA.

## Coleta futura

Quando implementada, deve registrar origem, autor, licença, URL e data quando aplicável, além de deduplicar e classificar o material antes de adicioná-lo à memória.

## Objetivo de produto

Receber um TXT com prompts, interpretar cada item, reutilizar a memória visual, compor rapidamente, refinar apenas quando necessário e entregar um ZIP pronto para o fluxo do CorvoQuiz/Forma.
