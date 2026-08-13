# DIREÇÃO V0.8 — REPROCESSAMENTO DIRECIONADO E LINHAGEM DE OPERAÇÕES

A V0.8 continua a arquitetura da V0.7 sem transformar o Engine em uma caixa-preta.

## Objetivo

Quando uma imagem está majoritariamente correta, o Engine não deve reconstruir toda a cena só porque uma região falhou.

Fluxo:

```text
OPERAÇÃO APROVÁVEL, MAS COM ERRO LOCAL
  ↓
GUIA DE CORREÇÃO [REPROCESS] + [FIX]
  ↓
CARREGA RESULTADO DA OPERAÇÃO PAI
  ↓
RESOLVE A REGIÃO
  ↓
EXPANDE CROP DE CONTEXTO
  ↓
REFINA SOMENTE O CROP
  ↓
RECOMBINA COM MÁSCARA SUAVE
  ↓
CRIA NOVA OPERAÇÃO FILHA
```

## Formato

```text
[REPROCESS]
reuse_previous_scene=true
preserve_character=true
preserve_pose=true
preserve_background=true
preserve_lighting=true

[FIX]
region=right_hand
action=redraw
problem=mao direita precisa ser corrigida
margin=0.28
feather=0.10
```

Também é possível usar caixa explícita:

```text
[FIX]
region=custom
box=62%,44%,18%,20%
action=redraw
```

`box=x,y,w,h` aceita pixels, proporções 0–1 ou porcentagens.

## Regiões

O resolvedor usa, nesta ordem:

1. `box=` explícito;
2. âncoras da pose (`head`, `character_box`, `object_target`);
3. heurística relativa ao `character_box` para mãos/braços;
4. fallback central conservador para nomes desconhecidos.

Toda resolução registra `source` e `confidence` no log. A heurística de mãos/braços não é tratada como detecção real de anatomia.

## Auditoria

A operação filha contém:

- `parent_operation_id`;
- guia base herdado;
- guia de correção;
- resultado original do pai;
- imagem antes/depois de cada FIX;
- máscara usada em cada FIX;
- caixa da região;
- prompt técnico local;
- backend, força, steps e tempo;
- referências herdadas;
- avaliação própria;
- ZIP independente.

O `logs/operacao.json` da operação pai recebe o ID da operação filha em `children`.

## Correção importante da biblioteca

A V0.8 corrige a resolução de caminhos de arquivos da `CORVO_LIBRARY`. Referências aprovadas selecionadas pelo Composer agora são abertas a partir da raiz real do projeto, em vez de serem tratadas como arquivos do `visual_bank/`.

## Limites atuais

- mãos e braços ainda usam heurística se a pose não fornecer âncoras específicas;
- não há detector de esqueleto;
- o refinador SD.CPP continua recebendo o crop já composto, sem condicionamento simultâneo por múltiplas imagens auxiliares;
- correção regional não substitui um novo render quando `reuse_previous_scene=false`.
