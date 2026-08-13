# DIREÇÃO V0.6 — BENCHMARK DO REFINADOR

Prioridade desta versão: testar cedo o estágio mais pesado da arquitetura.

```text
COMPOSER → IMAGEM BASE → IMG2IMG DE BAIXA FORÇA → PNG FINAL
```

O benchmark mede carga do motor e tempos por imagem, separando a primeira execução das seguintes.

Backends de benchmark:

- `light_cpu`: baseline não generativo;
- `sdcpp_img2img`: refinador generativo via stable-diffusion.cpp.

Configuração inicial recomendada:

- 512×512;
- 3 steps;
- denoising strength 0.24;
- 5 prompts.

A decisão de continuar investindo em coleta/memória deve considerar principalmente a **média aquecida do refinador IA** e a diferença visual entre `before` e `after`.
