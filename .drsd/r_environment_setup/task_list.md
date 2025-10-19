
---

## 📄 Documento 3: `.drsd/task_list.md`


# TASK LIST - Sistema de Gestão de Ambiente R para macOS

**Projeto**: ASRL  
**Feature**: R Environment Setup  
**Data de Criação**: 18 de outubro de 2025  
**Status Geral**: 🔴 Não Iniciado

---

## ✅ LEGENDA

- 🔴 Não iniciado
- 🟡 Em progresso
- 🟢 Concluído
- ⏸️ Bloqueado
- ❌ Cancelado

---

## 📋 TASKS PRINCIPAIS

### 1. 🔴 Preparação do Ambiente

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 15 min  

**Subtasks**:
- [ ] Criar diretório `/docs` na raiz do projeto
- [ ] Verificar se `.install_r_packages/` existe e contém versões
- [ ] Confirmar ambiente R instalado para testes

**Critérios de aceite**:
- Diretório `/docs` criado
- Acesso aos arquivos de referência confirmado

---

### 2. 🔴 Criar Script de Instalação

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 1h 30min  
**Arquivo**: `/docs/install_r_packages.sh`

**Subtasks**:

#### 2.1. Estrutura Básica
- [ ] Criar arquivo `/docs/install_r_packages.sh`
- [ ] Adicionar shebang `#!/usr/bin/env bash`
- [ ] Adicionar `set -e` para exit on error
- [ ] Definir variáveis de cores (RED, GREEN, YELLOW, NC)
- [ ] Criar funções auxiliares: `print_info()`, `print_success()`, `print_error()`

#### 2.2. Verificação de Pré-requisitos
- [ ] Implementar verificação se comando `R` existe
- [ ] Exibir erro claro se R não estiver instalado
- [ ] Incluir instruções de instalação na mensagem de erro
- [ ] Implementar verificação de versão do R
- [ ] Garantir que versão seja >= 4.0
- [ ] Exibir erro se versão for insuficiente

#### 2.3. Instalação de Pacotes
- [ ] Criar array com 17 pacotes no formato `"pkg==version"`
- [ ] Usar versões de `.install_r_packages/install_r_packages.sh` como base:
  - bibliometrix==5.1.1
  - openalexR==2.0.1
  - gridExtra==2.3
  - pander==0.6.6
  - knitr==1.50
  - reshape2==1.4.4
  - ggplot2==4.0.0
  - jsonlite==2.0.0
  - openxlsx==4.2.8
  - magrittr==2.0.4
  - maps==3.4.3
  - htmlwidgets==1.6.4
  - wordcloud2==0.2.1
  - RColorBrewer==1.1.3
  - treemap==2.4.4
  - plotly==4.11.0
  - viridis==0.6.5
- [ ] Implementar instalação do pacote `remotes` se não existir
- [ ] Criar loop para processar cada pacote
- [ ] Para cada pacote: verificar se já está instalado com versão correta
- [ ] Se não: instalar usando `remotes::install_version()`
- [ ] Se sim: exibir mensagem "already installed"

#### 2.4. Relatório e Finalização
- [ ] Implementar contador de pacotes instalados
- [ ] Implementar contador de pacotes com falha
- [ ] Exibir relatório final colorido
- [ ] Adicionar permissões de execução: `chmod +x`

**Critérios de aceite**:
- Script criado e executável
- Verifica R instalado e versão
- Instala todos os 17 pacotes
- Idempotente (não reinstala se já correto)
- Output claro e colorido

---

### 3. 🔴 Criar Script de Captura de Versões

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 45 min  
**Arquivo**: `/docs/capture_r_versions.sh`

**Subtasks**:
- [ ] Criar arquivo `/docs/capture_r_versions.sh`
- [ ] Adicionar shebang e comentários explicativos
- [ ] Implementar captura de versões via Rscript
- [ ] Formato output: `pkg==version`
- [ ] Listar todos os 17 pacotes
- [ ] Salvar output em arquivo temporário
- [ ] (Opcional) Implementar atualização automática de `install_r_packages.sh`
- [ ] (Opcional) Implementar atualização automática de `r_environment_setup.md`
- [ ] Adicionar permissões de execução

**Critérios de aceite**:
- Script captura versões de todos os pacotes
- Output no formato correto
- Executável

---

### 4. 🔴 Executar Captura de Versões Reais

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 15 min  
**Dependência**: Task 2, Task 3

**Subtasks**:
- [ ] Garantir que ambiente R atual tem todos os pacotes instalados
- [ ] Executar `/docs/capture_r_versions.sh`
- [ ] Capturar output com versões exatas
- [ ] Atualizar array de versões em `install_r_packages.sh`
- [ ] Salvar versões capturadas para usar na documentação

**Critérios de aceite**:
- Versões reais capturadas do ambiente
- Script `install_r_packages.sh` atualizado com versões reais

---

### 5. 🔴 Criar Documentação

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 1h  
**Arquivo**: `/docs/r_environment_setup.md`

**Subtasks**:

#### 5.1. Estrutura do Documento
- [ ] Criar arquivo `/docs/r_environment_setup.md`
- [ ] Adicionar título e descrição
- [ ] Criar seção "Visão Geral"
- [ ] Criar seção "Pré-requisitos"

#### 5.2. Instalação do R
- [ ] Documentar instalação via Homebrew
- [ ] Documentar instalação via instalador oficial
- [ ] Incluir comandos de verificação (`R --version`)
- [ ] Adicionar link para CRAN

#### 5.3. Instalação dos Pacotes
- [ ] Documentar execução do script `install_r_packages.sh`
- [ ] Incluir comando completo com caminho
- [ ] Documentar permissões (`chmod +x`)

#### 5.4. Tabela de Pacotes
- [ ] Criar tabela Markdown com 17 pacotes
- [ ] Incluir versões exatas capturadas na Task 4
- [ ] Formato: | Pacote | Versão | Descrição |

#### 5.5. Verificação Manual
- [ ] Documentar comando para verificar versões instaladas
- [ ] Incluir exemplo de output esperado

#### 5.6. Troubleshooting
- [ ] Adicionar solução para "R não encontrado"
- [ ] Adicionar solução para erros de compilação (Xcode)
- [ ] Adicionar solução para conflitos de versão
- [ ] Adicionar solução para problemas de rede/CRAN

#### 5.7. Finalização
- [ ] Adicionar seção "Próximos Passos"
- [ ] Adicionar links úteis (Bibliometrix, CRAN)
- [ ] Revisar formatação Markdown

**Critérios de aceite**:
- Documento completo e bem formatado
- Instruções claras e diretas
- Tabela com 17 pacotes e versões reais
- Seção troubleshooting útil

---

### 6. 🔴 Testes e Validação

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 45 min  
**Dependência**: Task 2, Task 5

**Subtasks**:

#### 6.1. Teste do Script de Instalação
- [ ] Executar `./docs/install_r_packages.sh` no ambiente atual
- [ ] Verificar que pacotes já instalados não são reinstalados
- [ ] Verificar mensagens de output
- [ ] Confirmar que relatório final é exibido

#### 6.2. Teste de Idempotência
- [ ] Executar script novamente
- [ ] Confirmar que nenhum pacote é reinstalado
- [ ] Confirmar que script termina com sucesso

#### 6.3. Teste de Verificações
- [ ] (Opcional) Temporariamente remover R do PATH
- [ ] Executar script e verificar mensagem de erro
- [ ] Restaurar R no PATH

#### 6.4. Validação da Documentação
- [ ] Ler documentação de ponta a ponta
- [ ] Verificar que comandos estão corretos
- [ ] Verificar que versões na tabela correspondem ao script
- [ ] Verificar links funcionam

**Critérios de aceite**:
- Script executa sem erros
- Idempotência confirmada
- Documentação validada

---

### 7. 🔴 Integração com Projeto

**Status**: Não iniciado  
**Responsável**: Dev  
**Estimativa**: 15 min  
**Dependência**: Task 5, Task 6

**Subtasks**:
- [ ] (Opcional) Adicionar seção no `readme.md` linkando para `/docs/r_environment_setup.md`
- [ ] (Opcional) Adicionar nota de deprecação em `.install_r_packages/r_env_setup.md`
- [ ] Commitar todos os arquivos criados
- [ ] Atualizar documentação do projeto se necessário

**Critérios de aceite**:
- Arquivos commitados
- Documentação acessível

---

## 📊 RESUMO DE PROGRESSO

| Task | Status | Progresso |
|------|--------|-----------|
| 1. Preparação do Ambiente | 🔴 | 0% |
| 2. Criar Script de Instalação | 🔴 | 0% |
| 3. Criar Script de Captura | 🔴 | 0% |
| 4. Executar Captura de Versões | 🔴 | 0% |
| 5. Criar Documentação | 🔴 | 0% |
| 6. Testes e Validação | 🔴 | 0% |
| 7. Integração com Projeto | 🔴 | 0% |

**Progresso Geral**: 0/7 tasks concluídas (0%)

---

## 📝 NOTAS

- Usar `.install_r_packages/install_r_packages.sh` como referência para versões
- Manter `.install_r_packages/` para compatibilidade
- Foco em macOS, zsh, R 4.0+
- Priorizar clareza e reprodutibilidade

---

## 🔗 REFERÊNCIAS

- DRSD: `.drsd/dsd_r_environment_setup.md`
- Solicitação: `.drsd/development_request.md`
- Código existente: `.install_r_packages/`

---

**Última atualização**: 18 de outubro de 2025  
**Próxima revisão**: Ao iniciar Task 1