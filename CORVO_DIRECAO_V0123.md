# DIREÇÃO V0.12.3

Esta versão altera somente a confiabilidade temporal da busca.

Próximo teste: usar o guia do garfo V0.12.2 sem alterar prompt ou refinador.

Resultado esperado:
1. a operação não deve retornar 504;
2. se Openverse responder, deve entrar ao menos uma referência real;
3. se a busca falhar, o Engine deve retornar diagnóstico antes do limite da função;
4. só depois disso avaliamos Composer/refinador.
