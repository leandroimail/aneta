# Pendências de documentação resgatadas do OneDrive

Estado em 2026-09-05. Sete arquivos do sistema de agentes/docs **ainda estão
presos na nuvem OneDrive** como *dataless* (cloud-only) — o cliente precisa
sincronizar/logar para baixá-los. Eles são a parte do material resgatado que **ficou para trás** — ver a mensagem do
commit `feat(agents)` (o resgate em si; estes 7 ficaram cloud-only e não entraram nele).

## Arquivos pendentes

| Arquivo | Papel |
|---|---|
| `AGENTS.md` | **Fonte única das regras do facilitador** (referenciado por `docs/tecnica/facilitador.md` e pelos agentes) |
| `CLAUDE.md` | Stub que aponta para o AGENTS.md |
| `docs/tutorial.md` | Tutorial de entrada da documentação |
| `docs/tecnica/pipeline.md` | Referência completa das flags do `aneta.py` (citada por `docs/como-fazer/executar.md`) |
| `docs/tecnica/busca-dsl.md` | Referência da DSL de busca (citada por `arquitetura.md` e `configuracao.md`) |
| `docs/tecnica/saidas-funil.md` | Referência das saídas do funil (citada por `arquitetura.md`) |
| `docs/como-fazer/aquisicao-pdfs.md` | How-to de aquisição de PDFs |

Até eles chegarem, os links para estes arquivos quebram (5 links known-affected).

## Como completar

1. Abra o OneDrive e faça login (a pasta é
   `~/Library/CloudStorage/OneDrive-Pessoal/Projects/python/asrl`).
2. Espere sincronizar e rode, na raiz do repo (o script pressupõe o checkout padrão
   em `~/Documents/asrl` — ajuste SRC/DST nele se o repo morar em outro lugar):
   ```bash
   bash completar_copia_onedrive.sh
   ```
3. Confira o conteúdo (estes arquivos NUNCA foram commitados — revisão humana
   recomendada) e commite. O script se auto-remove ao terminar (apenas se os 7 forem copiados — em caso de
falha ele fica para retry).

## Nota

O restante do resgate (agentes, skills, demais docs) já está versionado — ver
commit `feat(agents)`. O módulo legado `LLMGenerateSystematicReview.py` (geração
do artigo da revisão) e as specs `.kiro/bibliometry-fix` vivem apenas na linha
git divergida dentro da nuvem OneDrive e estão arquivados em
`Sandbox/legacy-linha-onedrive-2025-12/` (gitignored) — ver `README-LEGADO.md`.
