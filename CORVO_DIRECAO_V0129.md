# DIREÇÃO V0.12.9 — OPERAÇÃO PERTENCE AO BROWSER

Para o MVP em Vercel, não tratar `/tmp` como armazenamento persistente entre requisições.

A Function deve concluir tudo o que precisa do filesystem temporário dentro da mesma chamada. Antes de responder, ela envia para o navegador os metadados e as referências exatas utilizadas.

Depois disso o navegador é responsável por:
- executar o refinador browser-first;
- guardar o resultado final da operação em memória;
- montar e baixar o ZIP completo.

Assim `Exportar operação` continua funcionando mesmo que a instância Vercel que realizou a busca/composição já tenha sido descartada.

Não adicionar Vercel Blob apenas para resolver o MVP de exportação. Persistência remota pode ser avaliada depois, se houver necessidade de histórico online permanente.
