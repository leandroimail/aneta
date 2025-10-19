# SOLICITAÇÃO FORMAL DE DESENVOLVIMENTO
## Sistema de Gestão de Ambiente R para macOS

---

**Para**: Time de Desenvolvimento  
**De**: Arquitetura de Software  
**Referência**: DRSD-R-Environment-Setup  
**Data**: 18 de outubro de 2025  
**Prioridade**: MÉDIA  

---

## SUMÁRIO EXECUTIVO

Solicita-se a **criação de documentação e scripts de instalação** para o ambiente R necessário ao projeto ASRL, com foco em **reprodutibilidade** através de versões travadas de pacotes.

---

## ENTREGÁVEIS SOLICITADOS

### 1. Documentação: `/docs/r_environment_setup.md`

Documento Markdown com instruções completas para:
- Instalação do R 4.x no macOS
- Execução do script de instalação de pacotes
- Lista de 17 pacotes com versões travadas
- Troubleshooting básico

**Requisitos**:
- Instruções diretas, sem ambiguidade
- Comandos específicos para macOS/zsh
- Seção de troubleshooting com soluções práticas
- Tabela formatada com pacotes e versões

---

### 2. Script: `/docs/install_r_packages.sh`

Script bash para instalação automatizada dos pacotes R.

**Funcionalidades obrigatórias**:
- ✅ Verificar se R está instalado
- ✅ Verificar versão do R >= 4.0
- ✅ Instalar 17 pacotes com versões fixadas
- ✅ Usar `remotes::install_version()` para controle de versões
- ✅ Idempotência (não reinstalar se versão correta já existe)
- ✅ Output colorido e informativo
- ✅ Relatório final de sucesso/falhas

**Especificações técnicas**:
```bash
#!/usr/bin/env bash
set -e

# Verificações:
# 1. R instalado?
# 2. R versão >= 4.0?
# 3. Para cada pacote: instalado com versão correta?

# Pacotes (usar versões de .install_r_packages/ como base):
# bibliometrix==5.1.1, openalexR==2.0.1, etc.
```

---

### 3. Script Auxiliar: `/docs/capture_r_versions.sh`

Script para desenvolvedores capturarem versões instaladas.

**Funcionalidades**:
- Listar versões de todos os 17 pacotes
- Output no formato `pkg==version`
- (Opcional) Atualizar automaticamente os outros arquivos

---

### 4. Execução e Validação

**IMPORTANTE**: Após criar os scripts:

1. Executar `capture_r_versions.sh` no ambiente atual
2. Capturar versões exatas instaladas
3. Atualizar `install_r_packages.sh` com essas versões
4. Atualizar `r_environment_setup.md` com essas versões
5. Testar `install_r_packages.sh` para validar funcionamento

---

## CONTEXTO DO PROJETO

O projeto ASRL usa R para análises bibliométricas via pacote `bibliometrix`. Atualmente:

- ✅ Já existe implementação em `.install_r_packages/` com versões travadas
- ❌ Documentação misturada no `readme.md`
- ❌ Sem verificação de pré-requisitos (R instalado)
- ❌ Localização não intuitiva (diretório oculto)

**Objetivo**: Consolidar em `/docs` com documentação clara e scripts robustos.

---

## PACOTES R NECESSÁRIOS (17 total)

Com base na análise do código:

- `bibliometrix`
- `openalexR`
- `gridExtra`
- `pander`
- `knitr`
- `reshape2`
- `ggplot2`
- `jsonlite`
- `openxlsx`
- `magrittr`
- `maps`
- `htmlwidgets`
- `wordcloud2`
- `RColorBrewer`
- `treemap`
- `plotly`
- `viridis`

**Versões de referência**: Ver `.install_r_packages/install_r_packages.sh`

---

## CRITÉRIOS DE ACEITE

### Documentação
- [ ] `/docs/r_environment_setup.md` criado e completo
- [ ] Instruções de instalação do R (Homebrew + oficial)
- [ ] Tabela com 17 pacotes e versões
- [ ] Seção troubleshooting

### Scripts
- [ ] `/docs/install_r_packages.sh` funcional e com permissão de execução
- [ ] Verifica R instalado e versão >= 4.0
- [ ] Instala todos os pacotes com versões fixadas
- [ ] Idempotente (pode ser executado múltiplas vezes)
- [ ] `/docs/capture_r_versions.sh` criado

### Validação
- [ ] Scripts executados no ambiente atual
- [ ] Versões reais capturadas e documentadas
- [ ] Teste de instalação realizado com sucesso

---

## RISCOS CONHECIDOS

| Risco | Mitigação |
|-------|-----------|
| Erros de compilação no macOS | Documentar necessidade de Xcode Command Line Tools |
| Versões antigas não disponíveis | `remotes::install_version()` busca no archive do CRAN |
| Diferenças Intel/Apple Silicon | Testar em ambas arquiteturas se possível |

---

## DEPENDÊNCIAS

- Nenhuma dependência de código
- Requer R instalado para teste
- Usar versões do `.install_r_packages/` como referência

---

## OBSERVAÇÕES IMPORTANTES

⚠️ **CRÍTICO**: Não modificar código Python ou scripts R existentes. Apenas criar documentação e scripts de setup.

⚠️ **CRÍTICO**: Executar `capture_r_versions.sh` no ambiente atual para obter versões exatas reais.

✅ **RECOMENDADO**: Manter `.install_r_packages/` existente para compatibilidade com setups antigos.

✅ **FUTURO**: Considerar adicionar link no `readme.md` apontando para `/docs/r_environment_setup.md`.

---

## CONTATO

Para dúvidas ou esclarecimentos sobre esta solicitação:

- **Documento de requisitos completo**: `.drsd/dsd_r_environment_setup.md`
- **Task list**: `.drsd/task_list.md`
- **Arquiteto Responsável**: Sistema ASRL
- **Data de Solicitação**: 18 de outubro de 2025
- **Prazo Sugerido**: 1 sprint (2 semanas)
- **Status**: 🟡 Aguardando Início

---

## APROVAÇÕES

- [x] Requisitos validados
- [x] Análise de código existente concluída
- [x] Especificações técnicas definidas
- [x] Implementação aprovada para início

---
