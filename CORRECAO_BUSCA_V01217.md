# RECUPERAÇÃO DE PERSONAGEM E CENÁRIO — V0.12.17

## Caso Naruto + escola brasileira

Uma consulta longa como `Naruto Uzumaki full body transparent` passa a tentar primeiro:

```text
Naruto Uzumaki cosplay
Naruto Uzumaki
Naruto Uzumaki full body transparent
```

Para o fundo, o Engine tenta `sala de aula Brasil`, `sala de aula São Paulo` e `Brazil classroom` antes das frases longas. Se o guia autorizar cenário genérico, a exigência de localidade só é relaxada nas duas últimas tentativas. A evidência de sala de aula continua obrigatória.

O Commons fornece primeiro uma miniatura raster de até 1600 px e mantém o original como segunda URL. Isso reduz timeouts sem perder resolução útil.

A recuperação não afrouxa a identidade: um personagem nomeado precisa conter todos os tokens relevantes da identidade nos metadados. Se nenhuma referência licenciada e recortável existir, a falha continua explícita, conforme o `[FAIL_POLICY]`.

## Validação de deploy

Depois de publicar, abra `/api/health` e confirme:

```text
version=0.12.17
X-Corvo-Build=0.12.17-search-recovery
```
