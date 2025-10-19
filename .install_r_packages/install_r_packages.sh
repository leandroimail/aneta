#!/usr/bin/env sh
# Initial installer for R packages required by the project
# This script will install missing packages from CRAN. After first run,
# it will be updated to pin installed versions.

set -e

Rscript -e '
options(repos = c(CRAN = "https://cloud.r-project.org"))
packages_versions <- c(
  "bibliometrix==5.1.1",
  "openalexR==2.0.1",
  "gridExtra==2.3",
  "pander==0.6.6",
  "knitr==1.50",
  "reshape2==1.4.4",
  "ggplot2==4.0.0",
  "jsonlite==2.0.0",
  "openxlsx==4.2.8",
  "magrittr==2.0.4",
  "maps==3.4.3",
  "htmlwidgets==1.6.4",
  "wordcloud2==0.2.1",
  "RColorBrewer==1.1.3",
  "treemap==2.4.4",
  "plotly==4.11.0",
  "viridis==0.6.5"
)

# Use remotes::install_version to pin exact versions when available
if (!require("remotes", quietly = TRUE)) {
  install.packages("remotes")
}

for (pv in packages_versions) {
  parts <- strsplit(pv, "==")[[1]]
  pkg <- parts[1]
  ver <- parts[2]
  if (is.na(tryCatch(as.character(packageVersion(pkg)), error = function(e) NA))) {
    message("Installing ", pkg, " (", ver, ")...")
    remotes::install_version(pkg, version = ver, repos = "https://cloud.r-project.org")
  } else {
    installed_ver <- as.character(packageVersion(pkg))
    if (installed_ver != ver) {
      message(pkg, " has version ", installed_ver, "; updating/downgrading to ", ver)
      remotes::install_version(pkg, version = ver, repos = "https://cloud.r-project.org")
    } else {
      message(pkg, "==", ver, " already installed")
    }
  }
}
'

echo "R packages installation attempt finished."
