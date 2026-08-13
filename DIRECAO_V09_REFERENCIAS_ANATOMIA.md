# DIREÇÃO V0.9 — CONDICIONAMENTO POR REFERÊNCIAS + ANATOMIA OPCIONAL

A V0.9 transforma as referências auditáveis da V0.7/V0.8 em sinais que podem realmente chegar ao refinador.

## Objetivo

Separar quatro coisas que antes podiam parecer iguais:

1. referência selecionada pela biblioteca;
2. referência solicitada pelo guia;
3. referência realmente aceita pelo runtime generativo;
4. fallback quando o runtime/modelo não consegue aplicar esse condicionamento.

O Engine nunca deve registrar "identidade preservada por IP-Adapter" apenas porque uma imagem de referência existia. Ele só registra como **aplicado** quando o `stable-diffusion.cpp` anuncia a capacidade e a requisição nativa usa o campo correspondente.

## Fluxo V0.9

```text
GUIA
  ↓
REFERÊNCIAS SELECIONADAS
  ↓
REFERENCE CONDITIONING BUILDER
  ├─ identidade → imagem de personagem/rosto/roupa
  ├─ pose → referência de pose
  ├─ pose-control → esqueleto opcional via MediaPipe
  └─ extras → outras referências visuais
  ↓
SD.CPP CAPABILITIES
  ├─ ip_adapter_image disponível? → identidade
  ├─ control_image disponível? → pose-control
  ├─ ref_images disponível? → referências auxiliares
  └─ nada aplicável? → fallback V0.8
  ↓
LOG DE CONDICIONAMENTO
```

## Anatomia opcional

`engine/anatomy_locator.py` usa MediaPipe Pose Landmarker somente quando:

- o pacote `mediapipe` está instalado;
- existe `models/pose_landmarker.task` (ou caminho em `CORVO_POSE_LANDMARKER_MODEL`).

Quando disponível, ele produz regiões aproximadas para:

- cabeça/rosto;
- mão esquerda/direita;
- braço esquerdo/direito;
- torso;
- perna esquerda/direita;
- personagem/corpo.

Essas regiões têm prioridade no `[FIX]`. Sem detector, a V0.8 continua funcionando por âncoras da pose e heurística da caixa do personagem.

Também pode gerar uma imagem de esqueleto (`pose_control.png`) para ControlNet/OpenPose-like quando o backend aceitar `control_image`.

No reprocessamento regional, a V0.9 reutiliza **somente a referência de identidade** da operação pai. O pose-control de tela inteira é deliberadamente desativado no crop local para não deslocar mãos/rosto por coordenadas incompatíveis.

## Compatibilidade do refinador

A V0.9 consulta `/sdcpp/v1/capabilities` quando o servidor está pronto.

Campos que podem ser usados:

- `init_image` → composição base;
- `ip_adapter_image` → identidade/aparência;
- `control_image` → pose-control;
- `ref_images` → referências extras/model-dependent; não é registrado como preservação de identidade.

O caminho antigo `/sdapi/v1/img2img` continua como fallback de compatibilidade.

## Pesos auxiliares

A pasta `models/` pode conter pesos auxiliares, mas o Engine não deve confundi-los com o modelo principal.

A V0.9 exclui automaticamente do detector de modelo principal nomes de ControlNet, IP-Adapter, CLIP Vision e Pose Landmarker.

Carregamento automático conservador:

- ControlNet: somente quando o nome do modelo principal indica SD 1.5;
- IP-Adapter: somente quando o nome indica SD 1.5 ou SDXL e há também CLIP Vision;
- SD-Turbo padrão: permanece baseline e não recebe auxiliares automaticamente;
- modelo de família desconhecida: não recebe auxiliares automaticamente.

Para testes deliberados com um modelo compatível de nome não reconhecido, é possível definir:

```text
CORVO_FORCE_AUX_MODELS=1
```

Isso apenas força o carregamento; não garante compatibilidade dos pesos.

## Regra de auditoria

Os logs distinguem:

```text
conditioning_requested
conditioning_applied
conditioning_skipped
conditioning_fallback
reference_bundle
capability_features
```

Assim é possível descobrir se uma melhora veio realmente de identidade, pose, referências extras ou apenas do img2img tradicional.

## Instalação opcional da anatomia

No Windows:

```text
INICIAR.bat          # cria .venv
INSTALAR_ANATOMIA.bat
INICIAR.bat
```

O painel passa de `POSE FALLBACK` para `POSE PRONTA` quando pacote + modelo estiverem disponíveis.

## O que ainda não é a meta da V0.9

- treinar um refinador próprio;
- baixar automaticamente IP-Adapter/ControlNet;
- garantir compatibilidade de qualquer peso auxiliar;
- substituir o banco visual por embeddings generativos;
- detectar mãos com um Hand Landmarker dedicado.

A V0.9 é uma ponte auditável entre **referência selecionada** e **referência efetivamente usada pelo renderizador**.
