# Corvo Image Engine V0.10 — Vercel + Browser-first

## Papel do Vercel

O Vercel hospeda e distribui a interface e a API leve do Composer.

Ele **não precisa executar o refinador principal de IA**.

## Papel do navegador

O computador do usuário executa:

- detecção WebGPU;
- carregamento do runtime de IA;
- download/cache do modelo;
- inferência WebGPU ou WASM;
- geração do PNG final;
- ZIP do lote browser.

## Fluxo

```text
VERCEL
→ HTML / JS / CSS + Composer leve
→ navegador
→ WebGPU/WASM
→ modelo
→ PNG/ZIP
```

## Por que `/tmp` ainda existe

Algumas funções antigas do Engine ainda escrevem operações/biblioteca server-side. No Vercel elas continuam usando `/tmp` e devem ser tratadas como temporárias.

Isso não afeta o refinador browser, porque a inferência e o PNG final desse caminho ficam no cliente.

## Entry point

```text
engine.server:app
```

configurado em `pyproject.toml`.

## Endpoint de arquitetura

```text
GET /api/browser/config
```

retorna o runtime/modelo MVP e confirma que instalação local não é requisito.

## HTTPS

WebGPU deve ser usado em contexto seguro. Deploys Vercel são servidos por HTTPS, portanto são adequados ao fluxo browser-first.

## Legado local

`stable-diffusion.cpp`, Diffusers e Automatic1111 continuam no pacote, mas não fazem parte do caminho obrigatório V0.10.
