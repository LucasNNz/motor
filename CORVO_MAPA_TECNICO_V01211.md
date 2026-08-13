# CORVO IMAGE ENGINE V0.12.11 — ISOLAMENTO RECORTÁVEL

## Problema observado
A busca real trouxe 17 referências, mas todas foram rejeitadas pelo filtro `isolated=true`. A API e o download já estavam funcionando; o filtro tratava “isolado” como se a fonte precisasse chegar praticamente pronta.

## Correção
`isolated=true` passa a aceitar três caminhos auditáveis:
1. `transparent` — referência já possui alpha;
2. `isolated` — referência atinge o limiar visual estrito;
3. `cutout` — o fundo não é perfeito, mas é removível deterministicamente pelo Composer.

## Novos sinais
- `cutout_score`
- `cutout_compatible`
- `foreground_ratio`
- `border_foreground_ratio`
- `acceptance_mode`

## Composer
A remoção de fundo agora aceita também fundo claro de estúdio com pequena variação, usando estatística da borda. Fundo escuro/texturizado continua preservado/rejeitado.

## Busca do guia de teste
Primeiro tenta ilustração/PNG. Se não houver material utilizável, o guia libera busca fotográfica recortável. O Engine apenas executa a sequência.
