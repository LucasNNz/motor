# MAPA TÉCNICO — CORVO IMAGE ENGINE V0.10

## Baseline

Versão: `0.10.0`

Direção: `browser-first`

## Fluxo principal atual

```text
NAVEGADOR
  ↓
UI
  ↓
COMPOSER (API leve atual)
  ↓
PNG BASE
  ↓
BROWSER RUNTIME
  ├─ WebGPU preferido
  └─ WASM fallback
  ↓
TRANSFORMERS.JS IMAGE-TO-IMAGE
  ↓
PNG FINAL NO CLIENTE
```

## Arquivos novos/alterados principais

### `engine/static/browser_runtime.js`

Runtime de execução client-side.

Inclui:

- WebGPU detection;
- GPU adapter/limits;
- perfil estimado;
- compute benchmark;
- import dinâmico do Transformers.js;
- Cache API;
- WASM fallback;
- Swin2SR image-to-image;
- IndexedDB para histórico leve;
- exportação PNG no cliente.

### `engine/static/browser_models.json`

Manifest inicial de modelos e capacidades.

### `engine/static/index.html`

Novo painel Browser/WebGPU.

Também altera:

- geração única padrão para `COMPOSER + BROWSER AI`;
- lote padrão para `COMPOSER + BROWSER AI`;
- execução guiada padrão para `BROWSER AI`;
- backends nativos marcados como legado.

### `engine/static/app.js`

Integração do runtime browser com:

- diagnóstico;
- preparação do modelo;
- benchmark;
- preview antes/depois;
- geração única;
- execução guiada;
- lote sequencial;
- ZIP local com JSZip.

### `engine/server.py`

O servidor passa a declarar explicitamente a arquitetura browser-first e expõe:

```text
GET /api/browser/config
```

`/api/refiner/status` também descreve o refinador browser como caminho sem instalação local.

## Modelo MVP

```text
runtime: Transformers.js 3.8.1
task: image-to-image
model: Xenova/swin2SR-lightweight-x2-64
preferred device: WebGPU
fallback: WASM
```

### O que ele prova

- modelo de IA em browser;
- download sem instalador;
- cache no navegador;
- inferência local;
- processamento independente da Vercel Function;
- exportação local.

### O que ele NÃO prova

- prompt-guided img2img generativo;
- IP-Adapter browser;
- ControlNet browser;
- preservação de identidade por embedding;
- inpainting generativo;
- múltiplas referências condicionando um diffusion model.

Essas continuam como alvo da próxima etapa.

## Lote browser

O lote `composer_browser` não usa o job generativo do servidor.

Ele executa no cliente:

```text
PROMPT
→ POST /api/generate backend=composer
→ data URL
→ browserRuntime.refine()
→ Blob/URL local
```

Ao final importa JSZip via CDN e cria:

```text
<ID>.png
<ID>.png
...
manifest_browser.json
```

O ZIP é criado no navegador.

## Vercel

No Vercel:

- FastAPI continua servindo a UI e Composer;
- `/tmp` segue efêmero para dados server-side;
- SD.CPP não é iniciado;
- inferência do refinador principal não usa CPU/GPU do Vercel;
- GPU utilizada é a do computador que abriu a página.

## Cache

O runtime habilita:

```text
env.useBrowserCache = true
env.useWasmCache = true (quando disponível)
```

Em contexto não `crossOriginIsolated`, WASM é limitado a uma thread para evitar depender de headers COOP/COEP no MVP.

## Perfil automático

Heurística inicial:

- HIGH: RAM reportada >= 8 GB ou limite WebGPU grande;
- MEDIUM: RAM >= 4 GB ou limite intermediário;
- LOW: demais WebGPU;
- COMPATIBILITY: sem WebGPU.

Entrada de IA automática:

- HIGH: até 512 px;
- MEDIUM: até 384 px;
- LOW/compatibilidade: até 256 px.

O resultado é redimensionado para o tamanho original pedido pelo usuário.

## Pontos de atenção

1. O primeiro download depende atualmente do CDN do Transformers.js e do repositório do modelo.
2. Para independência maior, os mesmos artefatos podem ser espelhados depois em storage/CDN controlado pelo projeto.
3. Cache pode ser removido pelo usuário/navegador sob pressão de armazenamento.
4. WebGPU varia por navegador, GPU e driver.
5. O modelo MVP é refinador de detalhes, não o gerador/refinador guiado final.
6. Logs completos de operação ainda precisam migrar para exportação 100% client-side.

## Testes feitos no pacote

- compilação Python do servidor;
- sintaxe JS de `app.js`;
- sintaxe JS de `browser_runtime.js`;
- verificação de todos os IDs DOM usados pelo JS;
- import FastAPI com `VERCEL=1`;
- `/api/health` em modo Vercel;
- `/api/browser/config`;
- `/api/refiner/status`;
- arquivos estáticos browser servidos pela aplicação.

A inferência WebGPU real precisa ser medida no navegador/GPU do usuário, porque o ambiente de empacotamento não representa o PC final.
