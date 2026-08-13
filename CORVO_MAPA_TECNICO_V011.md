# CORVO IMAGE ENGINE V0.11 — REFINADOR MVP REAL (BROWSER-FIRST)

## Objetivo
Transformar o refinador web de prova técnica em um refinador MVP utilizável, eliminando sucesso falso e garantindo entrega visível.

## Principais mudanças
- pipeline do refinador browser agora valida se houve alteração perceptível;
- se a saída do modelo mudar pouco, o sistema aplica pós-processamento visual local antes de aceitar o resultado;
- preview DEPOIS e PNG baixado passam a usar exatamente o resultado final aceito;
- geração única também habilita o botão de download corretamente;
- metadados do refinamento mostram estratégia usada e percentual aproximado de mudança.

## Estratégias do refinador
- `model` → saída do modelo foi suficiente sozinha;
- `model+polish` → saída da IA recebeu polimento leve;
- `model+enhance` → saída da IA mudou pouco e foi reforçada;
- `enhance-only` → a IA foi insuficiente ou indisponível e o sistema entregou melhoria visual local.

## Regras de honestidade do pipeline
- o sistema mede a diferença entre imagem original e resultado;
- se a diferença for muito pequena, o resultado não é aceito como sucesso puro da IA;
- se mesmo após reforço a diferença continuar insuficiente, o usuário recebe erro de refino insuficiente.

## Observação importante
Este V0.11 ainda não é o refinador generativo guiado definitivo por identidade/pose/região. Ele é o primeiro refinador MVP **honesto e funcional** no navegador: roda localmente, muda a imagem de forma perceptível e garante consistência entre preview e download.
