# DIREÇÃO V0.12 — NÃO EXPANDIR ESCOPO

Para acelerar o MVP, qualquer nova implementação deve responder a uma destas perguntas:

1. o guia consegue mandar a ação?
2. o Engine consegue executar a ação?
3. o resultado melhora a produção real?
4. o erro fica auditável?

Não adicionar heurísticas de “inteligência geral” ao Engine. Ele é um executor visual orientado pelo TXT.

Prioridade seguinte: validar 3 a 5 guias reais de produção e medir onde falham. Só então trocar/fortalecer o provider visual correspondente.
