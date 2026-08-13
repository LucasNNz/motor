# Image Motor MVP

MVP inicial de um gerador separado, inspirado no fluxo client-side do Forma.

## Objetivo
Validar rapidamente a arquitetura:

- interface web simples
- motor local separado
- geração única
- geração em lote por TXT
- fila visual
- saída em PNG
- ZIP final por lote

## Estado atual
Esta versão já inclui:

- **backend FastAPI** com endpoints de health, system info, geração única, lote, cancelamento e download de ZIP
- **frontend web** servido pelo próprio backend
- **backend `mock`** funcional para validar toda a jornada de uso
- **backend `automatic1111`** funcional para integração com um motor local já rodando (Stable Diffusion WebUI / A1111)
- **backend `diffusers`** como _stub_ / ponto de integração futura para um modelo real embutido no próprio backend

> Importante: nesta versão, o modo `mock` já funciona sozinho. O modo `automatic1111` funciona se você já tiver um servidor local compatível rodando. O modo `diffusers` ainda depende de instalar e configurar um modelo de geração local.

## Estrutura

```text
image_motor_mvp/
  engine/
    backend.py
    models.py
    server.py
    utils.py
    static/
      index.html
      styles.css
      app.js
  outputs/
  requirements.txt
  README.md
```

## Como executar

### 1) Instalar dependências

```bash
pip install -r requirements.txt
```

### 2) Subir o servidor

```bash
cd engine
uvicorn server:app --reload --port 8011
```

### 3) Abrir no navegador

Acesse:

```text
http://localhost:8011
```

## Formato do TXT de lote

Uma linha por prompt:

```txt
UM GARFO CENTRALIZADO, ILUSTRAÇÃO 2D, FUNDO CLARO, SEM TEXTO
UMA COLHER CENTRALIZADA, ILUSTRAÇÃO 2D, FUNDO CLARO, SEM TEXTO
```

Ou com ID explícito:

```txt
001|UM GARFO CENTRALIZADO, ILUSTRAÇÃO 2D, FUNDO CLARO, SEM TEXTO
002|UMA COLHER CENTRALIZADA, ILUSTRAÇÃO 2D, FUNDO CLARO, SEM TEXTO
```

## Backends disponíveis

### 1) mock
Usado para validar rapidamente a experiência do produto.

- não depende de IA real
- gera imagens placeholder com o prompt gravado
- ideal para testar fila, ZIP e organização

### 2) automatic1111
Usa um servidor local compatível com a API do **Stable Diffusion WebUI (A1111)**.

Por padrão, tenta conectar em:

```text
http://127.0.0.1:7860
```

Endpoint esperado:

```text
POST /sdapi/v1/txt2img
```

Você pode alterar a URL pela interface.

### 3) diffusers
Ponto de integração futura para rodar um modelo diretamente no backend Python.

Hoje ele já está estruturado, mas depende de instalar pacotes como:

- diffusers
- transformers
- accelerate

...e de configurar o modelo local desejado.

## Próximos passos sugeridos

1. **Testar com Automatic1111 real**
   - subir o motor local
   - apontar a URL na interface
   - medir latência real por imagem

2. **Trocar o backend `diffusers` de stub para real**
   - instalar dependências no PC alvo
   - escolher um modelo rápido
   - medir latência local real

3. **Persistência local**
   - manter fila ao recarregar
   - reabrir jobs anteriores

4. **Mais telemetria**
   - tempo médio
   - ETA
   - log detalhado por item

5. **Refino do lote**
   - retry automático
   - seleção de subset para refazer
   - exportar manifesto JSON

6. **Integração futura tipo plugin/MCP**
   - expor `generate_batch()` e `get_status()` para o ChatGPT chamar diretamente

## Observação de arquitetura
A direção escolhida aqui é deliberada:

- **UI no navegador**
- **motor em localhost**

Isso preserva a experiência simples do Forma, mas deixa o processamento pesado fora das limitações do navegador.
