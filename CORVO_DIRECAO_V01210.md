# DIREÇÃO V0.12.10

O problema da última geração não estava no algoritmo de rotação: estava no contrato do guia. O TXT exportado não continha `orientation` nem `desired_view`, e o log confirmou `orientation_requested=null`.

A partir desta versão, guias `single_object_quiz` precisam declarar explicitamente orientação e vista. Para casos sem restrição, a IA externa deve escrever `orientation=free` e/ou `desired_view=free`.

Isso mantém o Engine como executor determinístico e impede que ele crie heurísticas semânticas para compensar decisões ausentes do planejamento externo.

Próximo teste do garfo: validar somente tamanho, verticalidade e centralização. A perspectiva frontal ainda depende da qualidade da referência/refinador visual; o Composer apenas executa geometria 2D.
