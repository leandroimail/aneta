# DRSD - Sistema de Gestão de Ambiente R para macOS

**Tipo**: Feature  
**Prioridade**: Média  
**Status**: Aguardando Implementação  
**Data de Criação**: 18 de outubro de 2025  
**Arquiteto Responsável**: Sistema ASRL

---

## 1. CONTEXTO E OBJETIVO

### Contexto
O projeto ASRL (Automated Systematic Review Library) é uma ferramenta Python para condução de revisões sistemáticas de literatura. O projeto utiliza R para análises bibliométricas através do pacote `bibliometrix` e outros pacotes complementares.

Atualmente existe documentação básica no `readme.md` e uma implementação preliminar em `.install_r_packages/`, mas:
- A documentação está misturada com outros conteúdos
- Não há verificação se o R está instalado
- Não há instruções específicas para instalação do R no macOS
- As versões já foram travadas anteriormente, mas precisam ser revalidadas

### Objetivo
Criar documentação standalone e scripts de instalação robustos para o ambiente R, garantindo:
1. **Reprodutibilidade**: Versões travadas de todos os pacotes
2. **Verificação de pré-requisitos**: Checagem se R está instalado
3. **Documentação clara**: Instruções diretas para macOS
4. **Localização adequada**: Documentos no diretório `/docs`

---

## 2. DESCRIÇÃO DA APLICAÇÃO/FEATURE SOLICITADA

### Feature: Sistema de Gestão de Ambiente R para macOS

**Componentes a serem criados:**

1. **Documento de Instalação** (`/docs/r_environment_setup.md`)
   - Instruções de instalação do R 4.x no macOS
   - Instruções de execução do script de instalação
   - Lista de pacotes com versões travadas
   - Troubleshooting básico

2. **Script de Instalação** (`/docs/install_r_packages.sh`)
   - Verificação se R está instalado
   - Verificação de versão mínima do R (4.0+)
   - Instalação de pacotes com versões fixadas
   - Verificação pós-instalação
   - Geração de relatório de versões instaladas

3. **Script de Captura de Versões** (`/docs/capture_r_versions.sh`)
   - Captura versões exatas instaladas no ambiente atual
   - Atualiza o script de instalação com versões travadas
   - Atualiza a documentação com as versões

---

## 3. REQUISITOS FUNCIONAIS

**RF01 - Verificação de Pré-requisitos**
- O script deve verificar se R está instalado no sistema
- Deve verificar se a versão do R é 4.0 ou superior
- Deve informar ao usuário como instalar o R se não estiver presente

**RF02 - Instalação de Pacotes com Versões Fixadas**
- Instalar todos os pacotes necessários:
  - bibliometrix, openalexR, gridExtra, pander, knitr
  - reshape2, ggplot2, jsonlite, openxlsx, magrittr
  - maps, htmlwidgets, wordcloud2, RColorBrewer
  - treemap, plotly, viridis
- Usar versões exatas (pinned versions)
- Usar `remotes::install_version()` para garantir versões específicas

**RF03 - Captura de Versões Instaladas**
- Script auxiliar deve listar todas as versões instaladas
- Formato de saída compatível com o script de instalação
- Deve atualizar automaticamente o script e a documentação

**RF04 - Documentação Clara**
- Instruções passo a passo para instalação do R no macOS
- Instruções de execução do script
- Lista completa de pacotes e versões
- Seção de troubleshooting

**RF05 - Relatório de Instalação**
- Exibir progresso durante instalação
- Informar quais pacotes foram instalados/atualizados
- Informar se algum pacote falhou
- Gerar sumário final

---

## 4. REQUISITOS NÃO FUNCIONAIS

**RNF01 - Compatibilidade**
- Sistema: macOS (Catalina 10.15+)
- Shell: zsh
- R: versão 4.0 ou superior
- CRAN repository: https://cloud.r-project.org

**RNF02 - Idempotência**
- Script pode ser executado múltiplas vezes sem efeitos colaterais
- Não reinstala pacotes se versão correta já estiver presente

**RNF03 - Clareza**
- Mensagens informativas durante execução
- Documentação em Markdown formatado
- Instruções diretas, sem ambiguidade

**RNF04 - Manutenibilidade**
- Versões centralizadas em uma única lista
- Fácil atualização de versões
- Código comentado

---

## 5. ANÁLISE DE CÓDIGO EXISTENTE

### Estrutura Atual

### Versões Já Travadas (Referência)

Do arquivo `.install_r_packages/install_r_packages.sh`:
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

**Total: 17 pacotes**

---

## 6. ARQUITETURA PROPOSTA

### Estrutura de Diretórios
/Users/.../asrl/
├── docs/ # NOVO
│ ├── r_environment_setup.md # Documentação principal
│ ├── install_r_packages.sh # Script de instalação
│ └── capture_r_versions.sh # Script auxiliar (dev only)
├── .install_r_packages/ # Manter para compatibilidade
└── readme.md # Link para docs/


### Fluxo de Instalação

1. Usuário executa `install_r_packages.sh`
2. Script verifica se R está instalado
3. Script verifica versão do R (>= 4.0)
4. Script instala pacote `remotes`
5. Para cada pacote na lista:
   - Verifica se já está instalado com versão correta
   - Se não: instala versão específica usando `remotes::install_version()`
   - Se sim: skip
6. Exibe relatório final

---

## 7. ESPECIFICAÇÕES TÉCNICAS

### 7.1. `/docs/r_environment_setup.md`

**Seções obrigatórias:**
1. Visão Geral
2. Pré-requisitos
3. Instalação do R (Homebrew + Instalador Oficial)
4. Instalação dos Pacotes R
5. Verificação Manual de Versões
6. Tabela de Pacotes e Versões Travadas
7. Troubleshooting
8. Próximos Passos

### 7.2. `/docs/install_r_packages.sh`

**Requisitos técnicos:**
- Shebang: `#!/usr/bin/env bash`
- `set -e` para exit on error
- Cores para output (RED, GREEN, YELLOW, NC)
- Funções: `check_command()`, `print_info()`, `print_success()`, `print_error()`
- Verificação de R instalado com mensagem de erro clara
- Verificação de versão do R >= 4.0
- Array de pacotes no formato `"pkg==version"`
- Loop de instalação usando `remotes::install_version()`
- Contador de sucessos/falhas
- Relatório final

### 7.3. `/docs/capture_r_versions.sh`

**Requisitos técnicos:**
- Captura versões via Rscript
- Output no formato `pkg==version`
- (Opcional) Atualização automática dos outros arquivos
- Comentários explicativos

---

## 8. CRITÉRIOS DE ACEITE

**CA01 - Documentação Completa**
- [ ] Arquivo `/docs/r_environment_setup.md` criado
- [ ] Inclui instruções de instalação do R no macOS
- [ ] Lista todos os 17 pacotes necessários
- [ ] Versões travadas documentadas
- [ ] Seção de troubleshooting presente

**CA02 - Script de Instalação Funcional**
- [ ] Arquivo `/docs/install_r_packages.sh` criado
- [ ] Possui permissões de execução (`chmod +x`)
- [ ] Verifica se R está instalado
- [ ] Verifica versão do R >= 4.0
- [ ] Instala todos os pacotes com versões exatas
- [ ] Não reinstala pacotes já instalados com versão correta
- [ ] Exibe progresso durante instalação
- [ ] Gera relatório final com sucessos/falhas

**CA03 - Script de Captura de Versões**
- [ ] Arquivo `/docs/capture_r_versions.sh` criado
- [ ] Captura versões de todos os pacotes
- [ ] Formato compatível com script de instalação

**CA04 - Execução e Validação**
- [ ] Script executado com sucesso no ambiente do desenvolvedor
- [ ] Versões exatas capturadas e documentadas
- [ ] Ambos os arquivos (script e docs) atualizados com versões reais
- [ ] Script validado em instalação limpa (se possível)

---

## 9. RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Incompatibilidade de versões | Baixa | Médio | Usar versões já validadas |
| Pacotes não disponíveis no CRAN | Baixa | Alto | `remotes::install_version()` busca em archive |
| Erros de compilação no macOS | Média | Médio | Documentar Xcode Command Line Tools |
| Diferenças Intel vs Apple Silicon | Baixa | Médio | Testar em ambas arquiteturas |

---

## 10. ESTRATÉGIA DE IMPLEMENTAÇÃO

### Ordem de Criação

1. Criar diretório `/docs`
2. Criar `/docs/install_r_packages.sh` (base funcional)
3. Criar `/docs/capture_r_versions.sh` (auxiliar)
4. Executar captura de versões
5. Atualizar `install_r_packages.sh` com versões reais
6. Criar `/docs/r_environment_setup.md` (documentação final)

### Estimativas

- **Tempo de desenvolvimento**: 2-3 horas
- **Tempo de teste**: 1 hora
- **Tempo de instalação (usuário final)**: 15-30 minutos

---

## 11. REFERÊNCIAS

- Implementação existente: `.install_r_packages/`
- CRAN: https://cloud.r-project.org
- Bibliometrix: https://www.bibliometrix.org
- remotes package: https://cran.r-project.org/web/packages/remotes/

---

**Documento gerado em**: 18 de outubro de 2025  
**Versão**: 1.0  
**Status**: Pronto para Implementação