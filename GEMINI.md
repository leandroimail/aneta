# Antigravity Agent Guidelines: Systematic Literature Review with Aneta (PI-FAST)

Este repositório implementa o pipeline sistemático **Aneta** para revisões da literatura (SLR / SMS), integrando agentes de IA e triagem multi-LLM local via harness **`pi-fast`**.

---

## Papel do Agente no Antigravity: SLR Orchestrator

Quando o usuário solicitar execução, progresso ou gerenciamento da revisão sistemática, o agente Antigravity atua como **SLR Orchestrator (Facilitador)**.

### Princípios Fundamentais
1. **Sempre Interativo (Human-in-the-Loop):** O orquestrador nunca decide a metodologia sozinho e nunca avança entre fases principais sem a confirmação explícita do usuário.
2. **Ambiente Python Confiável:** Qualquer execução de `aneta.py` deve sempre resolver o interpretador através do script de bootstrap do `aneta-runner`:
   ```bash
   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
   ```
3. **Segurança de Segredos:** Nunca imprima nem versione chaves de API (`config/.env` e `.data/` são estritamente gitignored).
4. **Idempotência e Retomada:** As etapas de busca, enriquecimento, triagem e download são cientes de DOI. Reexecutar pula artigos já concluídos.

---

## Fases do Pipeline Aneta

```
Fase 0: Setup          (protocol.md + config/*.yaml)
Fase 1: Busca          (--search → --enrich_async → --selection)
Fase 2: Abstract       (--abstract_classifier_llm_one_on_one_async → --process_responses → --filter_relevant_papers)
Fase 3: Aquisição      (--download_pdf_async / --download_pdf_assisted)
Fase 4: Full-Text      (--fulltext_classifier_llm_async → --process_responses_fulltext → --filter_final_papers)
Fase 5: Entrega        (--pipeline_report → --export_final)
```

---

## Skills Disponíveis em `.agents/skills/`

- `slr-orchestrator`: Orquestração global e coordenação do pipeline.
- `slr-status`: Detecção da fase atual e sumário do funil PRISMA sem chamadas de LLM.
- `aneta-runner`: Resolução e bootstrap seguro do interpretador Python.
- `slr-protocol`: Autoria de questões de pesquisa e critérios AC/RC.
- `slr-search-strategy`: Autoria de strings de busca DSL e filtros SQL DuckDB.
- `slr-inclusion-criteria`: Autoria e tuning de cláusulas SQL de votação.
- `slr-llm-config`: Configuração de painéis de LLMs e credenciais.
- `slr-pdf-acquisition`: Playbook de aquisição de PDFs e tratamento de bloqueios.
- `slr-decision-review`: Resumo de decisões e identificação de artigos limítrofes.
