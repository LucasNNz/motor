# CORVO IMAGE ENGINE V0.12.6 — REFERÊNCIA COMPOSICIONAL

## Diagnóstico que motivou a versão
A V0.12.5 finalmente completou o caminho busca externa → candidate → Composer → refino. Porém a referência escolhida era uma fotografia de um garfo sobre uma mesa de madeira. O Engine estava correto semanticamente (era um garfo), mas errado para a composição solicitada (objeto isolado, fundo simples e boa leitura de quiz).

## Correção do MVP
A V0.12.6 transforma diretivas já existentes no guia em critérios executáveis de seleção e montagem.

### Seleção
Quando o guia pede `isolated=true`, fundo simples/claro e rejeita `busy_background`, o coletor mede sinais visuais determinísticos:
- transparência;
- uniformidade da borda;
- textura da borda;
- brilho da borda;
- densidade de bordas;
- score de isolamento.

Esses sinais não são IA e não tentam interpretar a cena. Eles servem apenas para executar restrições explícitas do TXT.

### Ranking
Referências aprovadas pelo filtro recebem `composition_suitability`. O ranking da biblioteca considera esse valor para priorizar material adequado à montagem, além de qualidade/relevância/histórico.

### Composer
Para referências transparentes ou com fundo uniforme removível:
1. o fundo é removido heuristicamente;
2. o alpha real é recortado;
3. margens inúteis são descartadas;
4. `subject_scale`, `subject_x` e `subject_y` passam a ser aplicados ao objeto recortado, não ao retângulo original da fotografia.

### Auditoria
A operação passa a registrar também `composition_suitability` e `visual_metrics` da referência escolhida.

## O que não mudou
- busca fallback guiada permanece igual;
- Composer continua determinístico;
- refinador browser permanece o mesmo;
- o Engine não adiciona raciocínio semântico/LLM.
