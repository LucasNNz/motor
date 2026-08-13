# CORVO IMAGE ENGINE — MAPA TÉCNICO V0.9

## Baseline

Versão: `0.9.0`

Direção: biblioteca visual física + execução por guia + composição auditável + refinamento guiado + reprocessamento regional + condicionamento visual opcional.

## Fluxo principal guiado

```text
pedido_original
  +
guia_auxiliar
  ↓
guide_parser.py
  ↓
guided_service.py
  ├─ busca/seleção na CORVO_LIBRARY
  ├─ composer_engine.py
  ├─ reference_conditioning.py
  │    ├─ identidade
  │    ├─ pose
  │    ├─ pose-control opcional
  │    └─ refs extras
  ├─ refiner.py
  │    ├─ API nativa sdcpp com capabilities
  │    └─ fallback /sdapi/v1/img2img
  ↓
operation_manager.py
  ↓
resultado + referências + logs + avaliação + ZIP
```

## Módulos V0.9

### `engine/anatomy_locator.py`

Responsável por:

- detectar opcionalmente Pose Landmarker;
- converter landmarks em caixas de região;
- gerar esqueleto visual para pose-control;
- expor status/fallback.

Não é dependência obrigatória.

### `engine/reference_conditioning.py`

Cria `VisualReferenceBundle`:

- `identity_image`;
- `pose_image`;
- `control_image`;
- `extra_images`;
- metadados e forças derivadas de `[RENDER]`.

Prioridade atual de identidade:

```text
guide_character
→ composer_face
→ composer_outfit
```

Prioridade de pose:

```text
guide_pose
→ composer_pose
```

### `engine/refiner.py`

`SdCppImg2ImgRefiner` possui dois transportes:

1. `sdcpp_native_img_gen`
   - usado quando há referência solicitada e capability aplicável;
   - envia `init_image`, `ip_adapter_image`, `control_image` e/ou `ref_images`.

2. `sdapi_img2img_compat`
   - fallback da V0.8;
   - preserva funcionamento com builds antigos/sem pesos auxiliares.

`LightRefiner` continua como piso de velocidade e agora registra o bundle mesmo sem aplicá-lo aos pixels.

### `engine/sdcpp_manager.py`

Agora:

- consulta `/sdcpp/v1/capabilities`;
- detecta pesos auxiliares;
- não confunde pesos auxiliares com modelo principal;
- classifica conservadoramente família do modelo;
- só injeta flags auxiliares automaticamente quando a compatibilidade pode ser inferida;
- permite override consciente com `CORVO_FORCE_AUX_MODELS=1`;
- expõe `conditioning_compatibility` no status.

### `engine/reprocessor.py`

Ordem de resolução regional V0.9:

```text
box explícito
→ MediaPipe Pose Landmarker (se disponível)
→ âncora da pose
→ heurística da caixa do personagem
→ região central conservadora
```

A fonte e confiança continuam registradas. O reparo regional também pode reutilizar a referência de identidade da operação pai; pose-control global é desativado no crop local.

## Biblioteca visual

Mantém a estrutura V0.7/V0.8:

```text
CORVO_LIBRARY/
  CHARACTERS/
  POSES/
  FACES/
  EXPRESSIONS/
  CLOTHES/
  BACKGROUNDS/
  OBJECTS/
  LIGHTING/
  CAMERA/
  WEATHER/
  TEXTURES/
  STYLES/
  COMPOSITIONS/
```

Com estados:

```text
candidates/
approved/
rejected/
```

## Logs novos/relevantes

Por operação guiada:

```text
logs/condicionamento.json
logs/operacao.json
logs/buscas.json
logs/referencias.json
logs/composicao.json
logs/refinador.json
logs/tempos.json
logs/erros.json
logs/avaliacao.json
```

Quando pose-control é gerado:

```text
etapas/pose_control.png
```

No reprocessamento continuam:

```text
logs/reprocessamento.json
etapas/fix_*_mask.png
etapas/fix_*_before.png
etapas/fix_*_after.png
```

## Interface/API

Novos sinais visíveis:

- `anatomia: POSE PRONTA` ou `POSE FALLBACK`;
- refinador mostra se runtime anunciou IDENTIDADE / POSE / REFS;
- resultado guiado mostra condicionamento aplicado ou fallback.

Endpoint de diagnóstico:

```text
GET /api/refiner/status
```

retorna também:

```text
conditioning_features
visual_conditioning_ready
anatomy
```

## Instalação opcional

```text
INSTALAR_ANATOMIA.bat
requirements-anatomy.txt
scripts/setup_windows_anatomy.ps1
```

Baixa o Pose Landmarker Lite para:

```text
models/pose_landmarker.task
```

## Compatibilidade preservada

Continuam disponíveis:

- prompt/Composer antigo;
- coleta existente;
- biblioteca auditável;
- lote antigo;
- benchmark V0.6;
- reprocessamento V0.8;
- LIGHT CPU;
- SD.CPP img2img compatível.

## Limitações conhecidas

1. O setup padrão continua com `sd_turbo.safetensors` e, por segurança, não ativa automaticamente pesos auxiliares de família incompatível/desconhecida.
2. IP-Adapter/ControlNet reais dependem de pesos compatíveis colocados pelo usuário.
3. MediaPipe melhora localização corporal, mas não é um detector específico de detalhes de dedos/mãos.
4. Sem MediaPipe, pose-control não é gerado e o reparo volta ao fallback V0.8.
5. O refinador ainda é um backend externo genérico; o refinador pequeno/especializado próprio continua sendo objetivo futuro.

## Próximo gargalo provável

Depois de validar condicionamento real em hardware/modelo compatível:

- medir ganho de identidade/pose no benchmark;
- comparar combinações de referência por taxa de aprovação;
- adicionar detector de mãos/face somente se os logs mostrarem necessidade;
- tornar seleção de condicionamento dependente do tipo de cena;
- avaliar um preset de modelo SD1.5/SDXL especificamente para o pipeline de referência.
