# Corvo Image Engine V0.4 — Composer Engine

Esta versão muda a direção do projeto. O motor principal **não é mais um gerador diffusion pesado**.

O MVP agora testa a hipótese:

```text
PROMPT
  ↓
INTERPRETAÇÃO
  ↓
MEMÓRIA / BANCO VISUAL
  ↓
SELEÇÃO DE COMPONENTES
  ↓
COMPOSIÇÃO AUTOMÁTICA
  ↓
HARMONIZAÇÃO LEVE
  ↓
PNG
```

Não exige CUDA.

---

## Objetivo do MVP 1

Responder uma pergunta:

> A composição automática com memória visual consegue produzir imagens úteis para quiz sem precisar gerar todos os pixels do zero?

Nesta fase **não há coleta automática nem refinamento generativo pesado**.

---

# Teste rápido no Windows

1. Extraia o ZIP.
2. Execute:

```text
INICIAR.bat
```

3. No primeiro uso, o programa cria um ambiente Python e instala apenas dependências leves:

- FastAPI
- Uvicorn
- Pillow
- Requests

4. O navegador abre em:

```text
http://127.0.0.1:8011
```

5. Deixe o backend em:

```text
COMPOSER ENGINE
```

6. Clique em **Compor imagem**.

Não é necessário baixar modelo de vários GB para testar o Composer.

---

# Banco visual inicial

A pasta:

```text
visual_bank/
```

contém um banco demo criado proceduralmente pelo próprio MVP.

Atualmente possui:

- 10 fundos;
- 3 poses;
- 4 rostos/expressões;
- 9 combinações de roupas/poses;
- 10 objetos.

Total inicial: **36 assets**.

Os componentes possuem metadados em:

```text
visual_bank/metadata.json
```

O banco demo existe para validar a arquitetura, não para definir a qualidade visual final.

---

# Exemplos já entendidos pelo MVP

## Objeto simples

```text
UM GARFO CENTRALIZADO, BEM DESTACADO, FUNDO CLARO, SEM TEXTO
```

Interpretação esperada:

```text
MODO: object_only
FUNDO: bg_plain_light
OBJETO: obj_fork
```

## Cena composta

```text
UM MENINO NINJA SURPRESO APONTANDO PARA UMA CAIXA EM UMA FLORESTA
```

Interpretação esperada:

```text
FUNDO: bg_forest_day
POSE: pose_pointing_right
ROSTO: face_surprised
ROUPA: outfit_ninja_pointing_right
OBJETO: obj_box
```

A interface mostra esse plano antes/ao lado do resultado para facilitar o diagnóstico.

---

# Lote por TXT

Formato simples:

```txt
UM GARFO CENTRALIZADO, FUNDO CLARO, SEM TEXTO
UMA MAÇÃ CENTRALIZADA, FUNDO CLARO, SEM TEXTO
```

Ou com IDs:

```txt
001|UM GARFO CENTRALIZADO, FUNDO CLARO, SEM TEXTO
002|UMA MAÇÃ CENTRALIZADA, FUNDO CLARO, SEM TEXTO
```

O motor cria:

```text
001.png
002.png
manifest.json
```

E ao final disponibiliza o ZIP do lote.

---

# Como o Composer escolhe componentes

O MVP usa um interpretador local por palavras-chave/tags.

Ele tenta identificar:

- cenário/fundo;
- objeto principal;
- presença de personagem;
- pose;
- expressão;
- roupa;
- estilo básico.

Cada asset do banco possui tags. O motor calcula correspondência entre prompt e tags e seleciona o item mais adequado.

Esse interpretador é propositalmente simples nesta primeira prova de conceito. Futuramente pode ser substituído por um classificador/LLM local leve sem alterar a arquitetura do banco.

---

# Composição

O Composer usa:

- camadas RGBA;
- âncoras de cabeça/objeto;
- compatibilidade roupa ↔ pose;
- redimensionamento automático;
- sombras leves;
- harmonização não generativa de cor/contraste/nitidez.

A composição final é feita com Pillow/CPU.

---

# Direitos e licenças

Os assets demo desta versão são gerados proceduralmente pelo próprio MVP.

Ao adicionar referências externas, registrar quando aplicável:

- origem;
- URL;
- autor;
- licença;
- URL da licença;
- data de coleta;
- observações.

Um motor local não elimina obrigações de copyright/licença.

---

# Backends experimentais mantidos

A arquitetura antiga continua disponível para comparação:

- `SD.CPP · EXPERIMENTAL`
- `DIFFUSERS CPU · EXPERIMENTAL`
- `AUTOMATIC1111`
- `MOCK`

Eles **não são mais o caminho principal**.

Os scripts `INSTALAR_VULKAN.bat` e `INSTALAR_CPU.bat` permanecem no pacote apenas para experimentos futuros com refinamento generativo.

---

# Próximas fases

## MVP 1 — atual

```text
banco manual
→ interpretação
→ busca
→ composição
→ PNG
```

## MVP 2 — coleta automática

```text
conceito ausente
→ busca em fonte adequada
→ download
→ validação
→ deduplicação
→ registro de origem/licença
→ classificação
→ banco
```

## MVP 3 — refinador

Adicionar uma etapa pequena para:

- bordas;
- iluminação;
- cores;
- roupa/corpo;
- preenchimento;
- unificação de estilo.

Priorizar CPU / ONNX Runtime / DirectML / OpenVINO / outras opções sem CUDA.

---

# Estrutura principal

```text
image_motor_mvp/
  INICIAR.bat
  engine/
    backend.py
    composer_engine.py
    seed_visual_bank.py
    models.py
    server.py
    utils.py
    static/
  visual_bank/
    metadata.json
    LEIA-ME.txt
    assets/
      backgrounds/
      poses/
      faces/
      outfits/
      objects/
  outputs/
  sample_prompts.txt
  requirements.txt
```

---

# O que medir

No teste, medir principalmente:

- tempo por imagem;
- tempo para lote de 10;
- RAM;
- CPU;
- qualidade;
- legibilidade para quiz;
- consistência;
- sensação de colagem;
- porcentagem de prompts atendidos pelo banco;
- quais categorias precisam de mais assets;
- quanto refinamento seria realmente necessário.
