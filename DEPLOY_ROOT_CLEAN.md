# DEPLOY ROOT CLEAN — V0.12.16

1. O conteúdo deste ZIP deve ficar diretamente na raiz do repositório.
2. Na raiz do GitHub devem aparecer: VERSION.txt, DEPLOY_BUILD.txt, vercel.json, pyproject.toml, requirements.txt e engine/.
3. Não deve existir uma pasta externa corvo-image-engine-v01212/... envolvendo esses arquivos.
4. No Vercel, Root Directory deve apontar para a mesma raiz onde está VERSION.txt.
5. Faça um novo deployment sem reutilizar Build Cache.
6. Após publicar, abra /api/health e confirme version=0.12.16.
7. A resposta HTTP deve incluir X-Corvo-Build: 0.12.16-composite-contract.
