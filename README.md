# Corvo Image Engine V0.9 — Referências + Anatomia

> **V0.9 preserva a V0.8 e conecta a biblioteca visual ao refinador de forma auditável: identidade/pose podem virar condicionamento visual real quando o runtime suporta, e o reprocessamento pode usar anatomia opcional por Pose Landmarker.**

Arquitetura experimental atual:

```text
PEDIDO + GUIA AUXILIAR
  ↓
BUSCAS DIRIGIDAS + CORVO_LIBRARY
  ↓
COMPOSER GUIADO
  ↓
REFERENCE CONDITIONING BUNDLE
  ├─ identidade
  ├─ pose
  ├─ pose-control opcional
  └─ referências extras
  ↓
REFINADOR
  ├─ API NATIVA SD.CPP quando capabilities permitem
  └─ IMG2IMG V0.8 como fallback
  ↓
PNG + REFERÊNCIAS + LOGS + AVALIAÇÃO + ZIP
  ↓
[REPROCESS]/[FIX] → anatomia/âncoras/heurística → OPERAÇÃO FILHA
```

Arquivos de direção: `DIRECAO_V07_GUIA_BIBLIOTECA_AUDITORIA.md`, `DIRECAO_V08_REPROCESSAMENTO_DIRECIONADO.md` e `DIRECAO_V09_REFERENCIAS_ANATOMIA.md`.

## Novidades V0.9

- `engine/reference_conditioning.py`: transforma referências selecionadas em identidade, pose, pose-control e refs extras.
- `engine/anatomy_locator.py`: MediaPipe Pose Landmarker opcional; sem ele, o sistema usa os fallbacks da V0.8.
- `stable-diffusion.cpp` consultado por `/sdcpp/v1/capabilities`; o Engine só registra condicionamento como aplicado quando a capability correspondente foi realmente usada.
- suporte nativo opcional a `ip_adapter_image`, `control_image` e `ref_images`, mantendo identidade como IP-Adapter explícito.
- pesos auxiliares não podem mais ser confundidos com o modelo principal.
- carregamento automático conservador por família do modelo.
- `logs/condicionamento.json` por operação.
- painel mostra `POSE PRONTA/FALLBACK` e capabilities de referências.

## Anatomia opcional no Windows

Primeiro execute `INICIAR.bat` uma vez para criar `.venv`. Depois:

```text
INSTALAR_ANATOMIA.bat
```

Ele instala `mediapipe` e baixa `models/pose_landmarker.task`. Se não quiser instalar, nada quebra: o Engine continua usando âncoras e heurísticas.

## Condicionamento visual real

O setup padrão continua sendo o baseline com `sd_turbo.safetensors`. IP-Adapter/ControlNet **não são baixados automaticamente**. Coloque pesos compatíveis em `models/` e consulte `models/CONDICIONAMENTO_VISUAL.txt`. O Engine bloqueia carregamento automático quando não consegue inferir compatibilidade, em vez de fingir que o condicionamento foi aplicado.

---


## O que entrou na V0.6

### Benchmark dedicado do refinador
A interface possui agora a seção:

```text
BENCHMARK DO REFINADOR
```

Ela executa uma sequência de imagens e mede separadamente:

- tempo para carregar/iniciar o motor;
- tempo do Composer;
- tempo do refinador;
- tempo total por imagem;
- primeira imagem;
- média das imagens seguintes com o motor já carregado;
- mínimo / máximo;
- RAM do processo do motor quando disponível;
- antes/depois de cada teste.

O benchmark já compara a média aquecida com a referência operacional atual do Flow (~32 s por imagem considerando geração + margem de segurança).

---

## Dois refinadores para comparação

### 1. `LIGHT CPU`

Não é generativo.

Serve apenas como baseline de velocidade para sabermos quanto custa uma harmonização leve com Pillow/CPU.

### 2. `SD.CPP IMG2IMG`

É o teste decisivo.

Usa `stable-diffusion.cpp` e envia a composição pronta para:

```text
POST /sdapi/v1/img2img
```

com:

- imagem inicial;
- prompt original;
- `denoising_strength` baixo;
- poucos steps;
- saída PNG.

O objetivo é preservar a estrutura da composição e pedir ao modelo apenas a unificação/refinamento.

---

# Como testar no Windows

## PASSO 1 — extrair o ZIP

Extraia toda a pasta antes de executar.

## PASSO 2 — instalar o refinador Vulkan

Como os PCs não possuem CUDA, tente primeiro:

```text
INSTALAR_VULKAN.bat
```

Esse script:

1. baixa o build Windows/Vulkan mais recente do `stable-diffusion.cpp`;
2. instala o `sd-server` local;
3. baixa o modelo SD-Turbo na pasta `models/`.

O download do modelo é grande e acontece uma vez.

### Se Vulkan não funcionar

Execute:

```text
INSTALAR_CPU.bat
```

O modo CPU tende a ser mais lento, mas é importante como fallback de benchmark.

---

## PASSO 3 — iniciar o Corvo Image Engine

Execute:

```text
INICIAR.bat
```

Abra, se necessário:

```text
http://127.0.0.1:8011
```

---

# Benchmark recomendado

Na seção **Benchmark do Refinador**:

### Primeiro
Clique:

```text
TESTAR REFINO LEVE
```

Isso confirma que toda a infraestrutura do benchmark funciona.

### Depois
Clique:

```text
TESTAR IA · SD.CPP
```

Configuração inicial recomendada:

```text
512 × 512
3 steps
força img2img: 0.24
5 prompts
```

---

# Como interpretar

O programa gera um veredito automático usando a média das imagens após a primeira:

```text
≤ 10 s     → EXCELENTE
≤ 20 s     → MUITO PROMISSOR
≤ 30 s     → VIÁVEL PARA TESTE
≤ 45 s     → LIMÍTROFE
> 45 s     → LENTO DEMAIS PARA O FLUXO ATUAL
```

A **primeira imagem não é o principal número**, porque ela pode sofrer efeitos de aquecimento/cache mesmo depois de o modelo estar carregado.

O campo mais importante é:

```text
MÉDIA AQUECIDA
```

---

# Antes / Depois

Cada linha do benchmark cria:

```text
01_before.png
01_after.png
02_before.png
02_after.png
...
```

Na tabela existem links `ANTES` e `DEPOIS` para comparar visualmente se o ganho de qualidade justifica o custo de tempo.

Os resultados completos ficam em:

```text
outputs/refiner_benchmarks/<job_id>/
```

incluindo:

```text
benchmark.json
```

---

# O restante do projeto continua disponível

A V0.6 preserva:

- Composer Engine;
- banco demo;
- memória visual persistente;
- coletor Openverse;
- coletor Wikimedia Commons;
- filtro e deduplicação;
- lote por TXT;
- ZIP final;
- aprovação de assets da memória.

Mas, nesta versão, **o benchmark do refinador é a prioridade**.

---

# O que decidir depois do teste

## Se o refinador for rápido

Continuar com:

```text
MEMÓRIA VISUAL
→ COLETA MELHOR
→ COMPOSER MAIS INTELIGENTE
→ REFINADOR
→ LOTE
```

## Se for lento demais

Não investir tempo demais no refinador atual.

Testar alternativas como:

- outro modelo menor;
- quantização;
- outro backend sem CUDA;
- DirectML;
- ONNX Runtime;
- OpenVINO;
- refinamento não generativo mais sofisticado;
- refinamento apenas nas imagens que realmente precisam.

---

## Observação sobre direitos e licenças

A arquitetura local reduz dependência de serviços externos, mas não remove obrigações de copyright, licença de modelos ou licença dos assets utilizados.
