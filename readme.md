# Conceitos Básicos



# Regras básicas

## Enriquecimento

diretórios precisam estar com os nomes:

arxiv
ieee
science_direct
scopus
spring_nature
web_of_science
acm


### Bibtex estão na pastas
PATH_DATA + ".bibs"
precisa .bibs no final


# Configs



### impacts files
    Dados atualizados em Fevereiro de 2025 
        JCR referente a 2023
        SCIMAGO referente a 2025






Bibliometria

https://www.bibliometrix.org/vignettes/Introduction_to_bibliometrix.html

https://bibliometrix.org/documents/bibliometrix_Report.html

https://rforanalytics.com/06-method3.html

https://www.sciencedirect.com/science/article/pii/S1751157717300500

https://bibliometrix.org/biblioshiny/biblioshiny1.html

https://bibliometrix.org/biblioshiny/biblioshiny2.html



https://pt.slideshare.net/MassimoAria/bibliometrix-phd-seminar#2

https://github.com/NLeSC/litstudy/blob/master/notebooks/example.ipynb

https://colab.research.google.com/drive/1yHiMMZIKa-RrarXbPB9ca0gLN9YvvtPU?usp=sharing

https://www.vosviewer.com/features/screenshots

https://openalex.org/Visualizing_Science_Using_OpenAlex_and_VOSviewer.pdf

https://www.oaepublish.com/articles/jsegc.2022.09



Grafos:

https://github.com/medialab/ipysigma

exemplo: https://medium.com/@msdatashift/ipysigma-easily-visualize-networks-with-thousands-of-nodes-and-edges-in-python-3ecdbe0321de




instalar Python (colocar via linha de comando UV)
Instalar UV
Instalar R (via linha de comando)


usar R -> 
    R -e ' options(repos = c(CRAN = "https://cloud.r-project.org"));
           if (!require("devtools")) install.packages("devtools", repos = "https://cloud.r-project.org");
           if (!require("remotes")) install.packages("remotes", repos = "https://cloud.r-project.org");
           if (!require("bibliometrix")) install.packages("bibliometrix", repos = "https://cloud.r-project.org");
           if (!require("openalexR")) install.packages("openalexR", repos = "https://cloud.r-project.org");
           if (!require("gridExtra")) install.packages("gridExtra", repos = "https://cloud.r-project.org");
           if (!require("pander")) install.packages("pander", repos = "https://cloud.r-project.org");
          '

R -e 'options(repos = c(CRAN = "https://cloud.r-project.org"));
packages <- c(
  "bibliometrix",
  "openalexR",
  "gridExtra",
  "pander",
  "knitr",
  "reshape2",
  "ggplot2",
  "jsonlite",
  "openxlsx",
  "magrittr",
  "maps",
  "htmlwidgets",
  "wordcloud2",
  "RColorBrewer",
  "pandoc"
);


for (pkg in packages) {
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg, dependencies = TRUE)
  }
  library(pkg, character.only = TRUE)
};'


Linux: Use package manager (e.g., sudo apt-get install pandoc).
Macbook: Use package manager (e.g.,brew install pandoc).
Windows: Acesse o site oficial: https://pandoc.org/installing.html.
          choco install pandoc
          winget install --source winget --exact --id JohnMacFarlane.Pandoc

rum biblioshiny 
R -e 'library(bibliometrix); biblioshiny();'





## TODO: Implementar Bibliometria via Scopus, não apenas em OpenAlex
## TODO: Implementar download de pdf de forma assincrona


## TODO: Adicionar bibliometria e download de arquivos para final.bib além de select.bib
## todo: Adicionar bibliometria e download de arquivos para final.bib além de select.bib

## TODO: Implementar LLM Abstract assincrono
## TODO: Implementar parada e retomada por id do bibtex no one:one