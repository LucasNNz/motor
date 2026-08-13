# DIREÇÃO V0.10 — BROWSER-FIRST / REFINADOR WEB

## Decisão central

O Corvo Image Engine deixa de tratar um executável local instalado no Windows como caminho principal do refinador.

A direção passa a ser:

```text
VERCEL / HOST ESTÁTICO
        ↓
ENTREGA A INTERFACE
        ↓
NAVEGADOR DO USUÁRIO
        ├─ detecta WebGPU
        ├─ baixa o runtime/modelo quando necessário
        ├─ guarda os arquivos em cache do navegador
        ├─ executa a inferência localmente
        └─ exporta PNG/ZIP localmente
```

Não deve ser necessário instalar Python, CUDA, stable-diffusion.cpp, Automatic1111 ou um serviço local em cada computador.

## Por que isso combina com o projeto

O Corvo Image Engine já é orientado a componentes:

```text
GUIA
↓
BUSCA / MEMÓRIA VISUAL
↓
COMPOSER
↓
REFINADOR
↓
RESULTADO
```

Somente a localização do refinador muda. O contrato do refinador deve ser independente da tecnologia de execução.

## Runtime do navegador

A V0.10 introduz `engine/static/browser_runtime.js`.

Responsabilidades:

- detectar contexto seguro;
- detectar `navigator.gpu`;
- solicitar adaptador WebGPU;
- classificar a máquina em perfil LOW / MEDIUM / HIGH;
- executar benchmark compute simples;
- carregar Transformers.js somente quando necessário;
- usar Cache API para reaproveitar modelos;
- usar WebGPU como caminho preferido;
- cair para WASM quando WebGPU não estiver disponível;
- registrar execuções leves em IndexedDB;
- devolver PNG diretamente no cliente.

## Primeiro modelo de prova

O primeiro modelo não tenta resolver ainda o refinador generativo completo.

Ele usa:

```text
Transformers.js
TASK=image-to-image
MODEL=Xenova/swin2SR-lightweight-x2-64
```

Objetivo da V0.10:

> provar que uma imagem pode sair do Composer, entrar em um modelo de IA no navegador e voltar como PNG sem instalação local e sem inferência no servidor.

Esse modelo é adequado para reconstrução de detalhes/super-resolution. Ele NÃO deve ser confundido com o refinador generativo guiado final.

## Fallbacks

```text
WEBGPU disponível
→ executar IA na GPU do navegador

WEBGPU indisponível ou falhou
→ tentar WASM / CPU

modelo web indisponível
→ Composer continua utilizável sem IA
```

O Engine nunca deve bloquear todo o fluxo porque um backend de IA não está disponível.

## Cache

Transformers.js utiliza a Cache API do navegador quando disponível.

Fluxo esperado:

```text
PRIMEIRO USO
→ baixa runtime/modelo
→ guarda em cache

USOS SEGUINTES
→ consulta cache
→ evita download completo novamente quando o browser mantém os dados
```

O cache pertence ao perfil do navegador/computador. Ele não é uma instalação de programa.

## Lote browser

A V0.10 cria um modo de lote cliente:

```text
TXT
↓
para cada prompt:
  Composer leve
  ↓
  PNG base
  ↓
  Browser AI
  ↓
  PNG final local
↓
JSZip no navegador
↓
ZIP final
```

A IA e a compactação final acontecem no navegador.

## Execução guiada

Quando o guia usa:

```text
REFINADOR = BROWSER AI
```

o servidor executa apenas a composição. O navegador recebe a imagem-base e executa o refinador localmente.

Nesta V0.10 o ZIP de operação do servidor ainda registra a composição-base. A etapa futura é migrar a operação auditável inteira para armazenamento/exportação client-side, para que o PNG refinado e seus logs façam parte do mesmo ZIP sem depender de estado efêmero do Vercel.

## Contrato futuro do refinador generativo browser

O próximo refinador deve aceitar conceitualmente:

```text
base_image
prompt
mask opcional
identity_reference opcional
pose_reference opcional
scene_references opcionais
strength
preserve flags
```

E devolver:

```text
final_image
timings
device
model
conditioning_log
```

Isso permite trocar Swin2SR por um modelo generativo WebGPU/ONNX/WASM sem reescrever Composer, guia ou biblioteca.

## Legado local

Os módulos SD.CPP/Diffusers permanecem no repositório por comparação e fallback de desenvolvimento, porém:

- não são necessários para usar o caminho principal V0.10;
- aparecem como LEGADO LOCAL na interface;
- Vercel não tenta iniciá-los;
- o roadmap principal não depende deles.

## Próxima meta

Depois de provar o MVP em PCs reais:

1. medir tempo de download inicial;
2. medir tempo aquecido usando cache;
3. medir WebGPU em máquinas diferentes;
4. medir fallback WASM;
5. escolher/converter um refinador generativo pequeno compatível com browser;
6. implementar máscara/reprocessamento no cliente;
7. mover logs e ZIP completo da operação para o navegador.
