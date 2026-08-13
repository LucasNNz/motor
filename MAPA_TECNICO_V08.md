# MAPA TÉCNICO — CORVO IMAGE ENGINE V0.8

## Base preservada

A V0.8 mantém:

- execução por guia estruturado;
- coleta dirigida por `[SEARCH_*]`;
- filtros configuráveis;
- `CORVO_LIBRARY` física e auditável;
- Composer guiado;
- refinadores `light_cpu` e `sdcpp_img2img`;
- benchmark V0.6;
- logs e ZIP por operação;
- modo antigo por prompt como compatibilidade.

## Novo módulo: `engine/reprocessor.py`

Responsabilidades:

- resolver `[FIX] region=...`;
- aceitar `box=x,y,w,h` explícito;
- usar âncoras da pose quando disponíveis;
- gerar crop de contexto com `margin`;
- refinar somente o crop;
- gerar máscara suave com `feather`;
- recompor sem alterar o restante da imagem;
- registrar região, fonte, confiança, backend e tempo.

## `engine/guided_service.py`

Novo método `reprocess()`:

- recebe `parent_operation_id`;
- carrega o PNG final da operação pai;
- lê composição e referências já usadas;
- cria operação filha `regional_reprocess`;
- aplica um ou vários blocos `[FIX]` em sequência;
- copia as referências da operação pai;
- salva imagens intermediárias e máscaras;
- registra `logs/reprocessamento.json`;
- mantém avaliação independente da operação filha.

## `engine/operation_manager.py`

Agora suporta:

- `kind` da operação;
- `parent_operation_id`;
- lista `children`;
- leitura de JSON/TXT da operação;
- cópia das referências usadas pelo pai.

## `engine/composer_engine.py`

Correção crítica:

- ativos de `CORVO_LIBRARY/...` agora resolvem caminho na raiz do projeto;
- o plano auditável inclui `concept`, `title` e `anchors` quando presentes.

## API

Novo endpoint:

```text
POST /api/operations/{operation_id}/reprocess
```

Payload:

```json
{
  "correction_guide_text": "[REPROCESS]...",
  "refiner": "light_cpu",
  "steps": 3,
  "strength": 0.24
}
```

## Interface

A área de execução guiada ganhou:

- editor de guia `[REPROCESS]/[FIX]`;
- botão `Reprocessar região`;
- exibição de operação pai → filha;
- caixa usada em cada correção;
- backend e tempo do reprocessamento.

## Arquivos da operação filha

```text
operacao_.../
├── pedido_original.txt
├── guia_auxiliar.txt          # guia de correção
├── guia_base.txt              # guia da operação pai
├── guia_correcao.txt
├── resultado_final.png
├── referencias_usadas/
├── etapas/
│   ├── original_pai.png
│   ├── antes_refinamento.png
│   ├── fix_01_antes.png
│   ├── fix_01_mascara.png
│   ├── fix_01_depois.png
│   └── depois_refinamento.png
└── logs/
    ├── operacao.json
    ├── buscas.json
    ├── referencias.json
    ├── composicao.json
    ├── reprocessamento.json
    ├── refinador.json
    ├── tempos.json
    ├── erros.json
    └── avaliacao.json
```

## Próximo gargalo técnico

Depois da V0.8, o maior salto de qualidade não é mais de arquitetura de logs. É enriquecer o condicionamento visual do refinador e a localização anatômica:

1. âncoras específicas de mãos/pés/olhos;
2. detector de pose/esqueleto leve;
3. backend de inpainting/máscara nativo quando disponível;
4. condicionamento real por referência de identidade/pose, sem contaminar o canvas final;
5. benchmark comparando render total versus reparo local.
