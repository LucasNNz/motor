# DIREÇÃO DE TESTE V0.12.4

Esta versão corrige somente o armazenamento efêmero da biblioteca e remove resíduos de testes do pacote.

No próximo teste use o mesmo guia do garfo. O resultado esperado é que a referência encontrada possa ser persistida em `/tmp/CORVO_LIBRARY/.../candidates/` sem `Errno 2`.

Se a busca/refinamento apresentar outro erro depois disso, ele será tratado como o próximo gargalo isolado. Não ampliar o escopo até a cadeia mínima completar uma imagem.
