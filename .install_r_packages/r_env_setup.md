## Instruções para criar o ambiente R para o projeto

Este documento descreve os passos para criar um ambiente R com os pacotes necessários para executar os scripts de bibliometria do projeto.

Requisitos

- R (versão recomendada: 4.1 ou superior)
- Conexão com a internet para baixar pacotes do CRAN

Passos

1. Abra um terminal (zsh) na raiz do repositório do projeto.
2. Execute o script de instalação dos pacotes R fornecido: `.drsd/install_r_packages.sh`.

    - O script verificará pacotes já instalados e instalará os que estiverem faltando.
    - O script já está configurado para instalar versões travadas dos pacotes (para garantir reprodutibilidade).

3. Para conferir as versões instaladas manualmente, execute:

```sh
# lista de pacotes e versão
Rscript -e 'pkgs <- c("bibliometrix","openalexR","gridExtra","pander","knitr","reshape2","ggplot2","jsonlite","openxlsx","magrittr","maps","htmlwidgets","wordcloud2","RColorBrewer","treemap","plotly","viridis"); for (p in pkgs) { v <- tryCatch(as.character(packageVersion(p)), error = function(e) NA); cat(p, "==", v, "\n") }'
```

Pacotes e versões travadas

O script instala as seguintes versões exatas dos pacotes (geradas após a execução inicial):

- bibliometrix == 5.1.1
- openalexR == 2.0.1
- gridExtra == 2.3
- pander == 0.6.6
- knitr == 1.50
- reshape2 == 1.4.4
- ggplot2 == 4.0.0
- jsonlite == 2.0.0
- openxlsx == 4.2.8
- magrittr == 2.0.4
- maps == 3.4.3
- htmlwidgets == 1.6.4
- wordcloud2 == 0.2.1
- RColorBrewer == 1.1.3
- treemap == 2.4.4
- plotly == 4.11.0
- viridis == 0.6.5

Observações

- Se você quiser isolar o ambiente por projeto, considere usar `renv` ou containers (Docker). Este guia apenas instala pacotes globais no R do sistema.
- Se ocorrerem erros de compilação ao instalar algum pacote (especialmente pacotes que dependem de compilação C/C++), instale as ferramentas de desenvolvimento do sistema (Xcode Command Line Tools no macOS):

```sh
xcode-select --install
```

Script de instalação

- O script de instalação é `.drsd/install_r_packages.sh` e deve ser executado com `./.drsd/install_r_packages.sh`.

Fim.
