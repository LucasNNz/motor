# Corvo Image Engine V0.10 — Browser-first + WebGPU

A V0.10 muda a arquitetura principal do projeto.

## Objetivo

Abrir o Corvo Image Engine no navegador e usar a máquina do usuário para o refinamento de IA, sem instalar um backend separado em cada PC.

```text
VERCEL / WEB
   ↓
NAVEGADOR
   ↓
WEBGPU (preferido) ou WASM (fallback)
   ↓
REFINADOR DE IA
   ↓
PNG / ZIP LOCAL
```

O Vercel distribui a aplicação. A inferência pesada do refinador browser não acontece na Serverless Function.

## Uso

### No Vercel

Faça o deploy normalmente. Abra a página em HTTPS.

No topo aparecerá **Refinador no Navegador**.

1. O sistema detecta WebGPU automaticamente.
2. Clique **Preparar refinador**.
3. No primeiro uso o runtime/modelo é baixado.
4. O navegador usa Cache API quando disponível.
5. Escolha uma imagem ou gere uma imagem pelo Composer.
6. Clique **Refinar no navegador**.
7. Baixe o PNG diretamente do browser.

### Geração única

O backend padrão é:

```text
COMPOSER + BROWSER AI
```

Fluxo:

```text
prompt
→ Composer
→ imagem-base
→ refinador browser
→ preview final
```

### Lote por TXT

O backend padrão do lote é:

```text
COMPOSER + BROWSER AI · CLIENTE
```

Cada imagem é composta e depois refinada sequencialmente no navegador. Ao final, o próprio browser cria um ZIP contendo PNGs + `manifest_browser.json`.

### Execução guiada

O refinador padrão é:

```text
BROWSER AI · WEBGPU/WASM
```

O servidor monta a composição e o navegador executa a etapa de IA.

## Modelo usado no primeiro MVP

```text
Transformers.js 3.8.1
image-to-image
Xenova/swin2SR-lightweight-x2-64
```

Esse modelo é deliberadamente pequeno e serve para provar a arquitetura browser-first com reconstrução de detalhes/super-resolution.

**Ele ainda não é o refinador generativo guiado final.** Ainda não recebe prompt + identidade + pose + máscara como um diffusion img2img completo.

## Fallback

```text
WEBGPU → preferido
WASM   → fallback CPU no navegador
COMPOSER → continua funcionando mesmo sem modelo de IA
```

## Sem instalação local obrigatória

Para o caminho principal V0.10 você não precisa executar:

- `INSTALAR_VULKAN.bat`;
- `INSTALAR_CPU.bat`;
- `INSTALAR_ANATOMIA.bat`;
- stable-diffusion.cpp;
- Diffusers;
- Automatic1111.

Esses componentes foram mantidos apenas como **legado experimental/local** para comparação e desenvolvimento.

## Cache

O navegador pode guardar runtime e modelo no Cache API. Isso significa que outra sessão no mesmo perfil do browser pode reaproveitar os arquivos sem instalar um programa.

O cache pode ser limpo pelo botão **Limpar cache IA** ou pelo próprio navegador se o armazenamento for removido.

## Arquitetura anterior preservada

Continuam disponíveis:

- guia estruturado;
- busca dirigida;
- `CORVO_LIBRARY`;
- Composer;
- operações e avaliações server-side;
- reprocessamento local legado;
- SD.CPP legado.

A mudança principal é que o roadmap do refinador deixa de depender deles como runtime obrigatório.

## Documentos

- `DIRECAO_V10_BROWSER_FIRST.md`
- `MAPA_TECNICO_V10.md`
- documentos V07/V08/V09 continuam no pacote como histórico da arquitetura.

## Próximo passo

Substituir/expandir o refinador web MVP por um **refinador generativo guiado browser-compatible**, mantendo a mesma ideia:

```text
base_image
+ prompt
+ referências
+ pose
+ máscara opcional
→ WebGPU
→ imagem final
```
