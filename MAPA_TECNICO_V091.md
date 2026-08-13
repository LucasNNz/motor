# CORVO IMAGE ENGINE V0.9.1 — MAPA TÉCNICO

## Objetivo
Corrigir o crash de cold start no Vercel mantendo a arquitetura local-first da V0.9.

## Novo módulo
`engine/runtime_paths.py`

Detecta o ambiente e separa código empacotado de dados mutáveis.

### LOCAL
- `DATA_DIR = raiz do projeto`
- biblioteca persistente
- operations persistentes
- outputs persistentes
- processos locais permitidos

### VERCEL
- `DATA_DIR = /tmp/corvo-image-engine`
- biblioteca seed copiada para área mutável
- operations temporárias
- outputs temporários
- benchmark temporário
- `stable-diffusion.cpp` local bloqueado

## Entry point
`pyproject.toml`:

```toml
[tool.vercel]
entrypoint = "engine.server:app"
```

## Endpoints relevantes
- `GET /api/health` → inclui `runtime_mode` e `data_dir`
- `GET /api/deployment/status` → capacidades do ambiente
- `POST /api/engine/start` → local: normal; Vercel: 503 explicativo
- `POST /api/generate` → Composer/Mock funcionam em smoke test Vercel

## Correções de caminho
A biblioteca não é mais resolvida assumindo que todo `local_path` vive sob o diretório empacotado. `MemoryManager.path_for()` é a fonte de verdade para referências mutáveis.

Foram atualizados:
- `memory_manager.py`
- `composer_engine.py`
- `guided_service.py`
- `reference_conditioning.py`
- `server.py`
- `operation_manager.py`
- `refiner_benchmark.py`
- `sdcpp_manager.py`

## Testes realizados
1. `compileall` de `engine/`.
2. Self-test local do Composer.
3. JavaScript com `node --check`.
4. Simulação `VERCEL=1`:
   - `/api/health` = 200
   - `/api/deployment/status` = 200
   - `/api/system` = 200
   - `/` = 200
   - geração Composer 256×256 = 200
   - `/api/engine/start` = 503 controlado
5. Repetição do smoke test com a árvore do projeto sem permissão de escrita e processo executado como usuário não privilegiado; health, página e Composer continuaram em 200.

## Limite arquitetural que permanece
Vercel Function não substitui o worker local do Corvo Image Engine. A V0.9.1 impede crash e permite hospedar/testar o plano de controle leve. O refinador generativo, persistência física auditável e tarefas longas continuam locais até existir um worker remoto dedicado.
