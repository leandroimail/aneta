# Checking if required packages are installed and installing them if necessary
options(repos = c(CRAN = "https://cloud.r-project.org"))
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
  "treemap"
)


for (pkg in packages) {
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg, dependencies = TRUE)
  }
  library(pkg, character.only = TRUE)
}

# Load required libraries
library(bibliometrix)
library(pander)
library(knitr)
library(reshape2)
library(ggplot2)
library(jsonlite)
library(openalexR)
library(gridExtra)
library(openxlsx)
library(ggplot2)
library(magrittr)
library(maps)
library(htmlwidgets)
library(wordcloud2)
library(RColorBrewer)
library(treemap)

# No início do script, após definir path_save
pdf(file = NULL) # Desativa o dispositivo PDF padrão

# Function to record logs
log_message <- function(message, level = "INFO", log_file) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  full_message <- paste0("[", level, "] ", timestamp, " - ", message, "\n")
  cat(full_message)
  cat(full_message, file = log_file, append = TRUE)
}


# Auxiliary function to save network plots
save_network_plot <- function(network_plot, filename, path_save, log_file) {
  # Set plot theme
  theme_set(theme_bw())

  if (!is.null(network_plot)) {
    png(file.path(path_save, filename),
      width = 10, height = 8, units = "in", res = 300
    )
    plot(network_plot$graph)
    log_message(paste(filename, "saved successfully."), "INFO", log_file)
  }
}


save_plot <- function(plot_obj, filename, width = 8, height = 6) {
  # Set plot theme
  theme_set(theme_bw())

  full_path <- file.path(path_save, filename)
  tryCatch(
    {
      ggsave(
        filename = full_path,
        plot = plot_obj,
        width = width,
        height = height,
        bg = "white" # Adds white non-transparent background
      )
      log_message(paste("Plot saved in:", full_path), "INFO", log_file)
    },
    error = function(e) {
      log_message(
        paste("Error when saving plot in", full_path, ":", e$message),
        "ERROR",
        error_log_file
      )
    }
  )
}


# Define environment variables and paths
path_data <- Sys.getenv("PATH_DATA", ".data")
base_path <- Sys.getenv("PROJECT_PATH")

# Set path to save plots and logs
path_save <- file.path(base_path, ".data", "BIBLIOMETRY")

# Check if error_fetch_openalex.log exists and make a backup if it does
error_log_path <- file.path(path_save, "error_fetch_openalex.log")
has_error_log <- FALSE
error_log_content <- NULL

if (file.exists(error_log_path)) {
  has_error_log <- TRUE
  error_log_content <- readLines(error_log_path, warn = FALSE)
}

# Delete the directory if it exists
if (dir.exists(path_save)) {
  unlink(path_save, recursive = TRUE)
}

# Create the directory
dir.create(path_save, recursive = TRUE)

# Restore the error log if it existed
if (has_error_log && !is.null(error_log_content)) {
  writeLines(error_log_content, error_log_path)
}

# Define log files
log_file <- file.path(path_save, "execution.log")
error_log_file <- file.path(path_save, "error.log")

log_message("Script execution started.", "INFO", log_file)

# Building the absolute path of the JSON file
relative_path <- file.path(path_data, "OUTPUTS", "openalex_metadata.json")
absolute_path <- file.path(base_path, relative_path)
final_path <- normalizePath(absolute_path, mustWork = FALSE)

log_message(paste("Input JSON file:", final_path), "INFO", log_file)


# Reading the JSON file with exception handling
data_json <- tryCatch(
  {
    log_message("Attempting to read the JSON file.", "INFO", log_file)
    fromJSON(final_path, simplifyDataFrame = FALSE)
  },
  error = function(e) {
    log_message(paste("Error reading JSON file:", e$message), "ERROR", error_log_file)
    NULL
  }
)

if (is.null(data_json)) {
  log_message("Stopping execution due to failure in reading JSON.", "ERROR", error_log_file)
  stop("JSON file could not be read.")
}


# Convert JSON data to 'works' dataframe and perform descriptive analysis
df_works <- tryCatch(
  {
    log_message("Converting JSON data to 'works' dataframe.", "INFO", log_file)
    oa2df(data_json, entity = "works")
  },
  error = function(e) {
    log_message(paste("Error converting JSON data:", e$message), "ERROR", error_log_file)
    NULL
  }
)

if (is.null(df_works)) {
  log_message("Stopping execution due to failure in converting data.", "ERROR", error_log_file)
  stop("DataFrame not created.")
}


# Generating bibliometric results
bibliometrics_data <- tryCatch(
  {
    log_message("Performing bibliometric analysis with oa2bibliometrix.", "INFO", log_file)
    M <- oa2bibliometrix(df_works)
    res_analysis <- biblioAnalysis(M, sep = ";")
    summary_res <- summary(res_analysis, k = 30, pause = FALSE, verbose = FALSE)
    result <- list(M = M, res = res_analysis, summary = summary_res)

    # Save bibliometrics_data as an R dataframe with exception handling
    tryCatch(
      {
        saveRDS(M, file = file.path(path_save, "bibliometry_data.rds"))
        log_message("Bibliometrics data saved as RDS file.", "INFO", log_file)
      },
      error = function(e) {
        log_message(paste("Error saving RDS file:", e$message), "ERROR", error_log_file)
      }
    )
    result
  },
  error = function(e) {
    log_message(paste("Error in bibliometric analysis:", e$message), "ERROR", error_log_file)
    NULL
  }
)

if (is.null(bibliometrics_data)) {
  log_message("Stopping execution due to failure in bibliometric analysis.", "ERROR", error_log_file)
  stop("Bibliometric analysis not performed.")
}


# Recording main information and productive authors
main_information <- bibliometrics_data$summary$MainInformationDF
most_prod_authors <- bibliometrics_data$summary$MostProdAuthors
most_cited_papers <- bibliometrics_data$summary$MostCitedPapers

log_message("Summary of main information and productive authors extracted.", "INFO", log_file)
pander(main_information, caption = "Summary Information")
pander(most_prod_authors, caption = "Most Productive Authors", table.split = Inf)
pander(most_cited_papers, caption = "Most Cited Papers")


# Saving dataframes as Excel files
tryCatch(
  {
    log_message("Saving dataframes as Excel files.", "INFO", log_file)

    # Main Information
    write.xlsx(main_information,
      file.path(path_save, "main_information.xlsx"),
      rowNames = TRUE
    )

    # Most Productive Authors
    write.xlsx(most_prod_authors,
      file.path(path_save, "most_productive_authors.xlsx"),
      rowNames = TRUE
    )

    # Most Cited Papers
    write.xlsx(most_cited_papers,
      file.path(path_save, "most_cited_papers.xlsx"),
      rowNames = TRUE
    )

    log_message("Excel files saved successfully.", "INFO", log_file)
  },
  error = function(e) {
    log_message(paste("Error saving Excel files:", e$message), "ERROR", error_log_file)
  }
)


# Basic analysis plot
plot_basic <- tryCatch(
  {
    log_message("Generating basic analysis plot.", "INFO", log_file)
    plots <- plot(bibliometrics_data$res, pause = FALSE)

    # Save each individual plot
    save_plot(plots[[1]], "most_productive_authors.png")
    save_plot(plots[[2]], "most_productive_countries.png")
    save_plot(plots[[3]], "annual_scientific_production.png")
    save_plot(plots[[4]], "average_article_citation.png")

    plots # returns the list of plots
  },
  error = function(e) {
    log_message(paste("Error generating basic analysis plot:", e$message), "ERROR", error_log_file)
    NULL
  }
)


# Plot: Author Production Over Time
plot_author_prod <- tryCatch(
  {
    log_message("Generating Author Production Over Time plot.", "INFO", log_file)
    top_authors <- authorProdOverTime(bibliometrics_data$M, k = 10, graph = TRUE)
    top_authors
  },
  error = function(e) {
    log_message(paste("Error in Author Production plot:", e$message), "ERROR", error_log_file)
    NULL
  }
)

if (!is.null(plot_author_prod)) {
  ggsave("author_production_top10.png", plot = plot_author_prod$graph, path = path_save)
}


# Plot: Author collaboration network
tryCatch(
  {
    log_message("Generating Author Collaboration Network.", "INFO", log_file)
    net_matrix_authors <- biblioNetwork(
      bibliometrics_data$M,
      analysis = "collaboration",
      network = "authors",
      sep = ";"
    )
    net_authors <- networkPlot(
      net_matrix_authors,
      n = 50,
      Title = "Author Collaboration",
      type = "auto",
      cluster = "louvain",
      size.cex = TRUE,
      edgesize = 2,
      labelsize = 0.75,
      noloops = TRUE,
      halo = FALSE,
      curved = TRUE,
      label.color = TRUE,
      community.repulsion = 0.0075
    )
    save_network_plot(net_authors, "author_collaboration_network_top50.png", path_save, log_file)
  },
  error = function(e) {
    log_message(
      paste("Error in Author Collaboration Network:", e$message),
      "ERROR",
      error_log_file
    )
  }
)


# Plot: Keyword Co-occurrences
tryCatch(
  {
    log_message("Generating Keyword Co-occurrences plot.", "INFO", log_file)
    net_matrix_keywords <- biblioNetwork(bibliometrics_data$M, analysis = "co-occurrences", network = "keywords", sep = ";")
    net_keywords <- networkPlot(net_matrix_keywords,
      normalize = "association",
      n = 50, Title = "Keyword Co-occurrences",
      type = "fruchterman",
      cluster = "louvain",
      size.cex = TRUE, edgesize = 2, labelsize = 0.75,
      noloops = TRUE,
      halo = FALSE, curved = TRUE,
      label.color = TRUE,
      community.repulsion = 0.0075
    )
    save_network_plot(net_keywords, "keyword_cooccurrences_top50.png", path_save, log_file)
  },
  error = function(e) {
    log_message(paste("Error in Keyword Co-occurrences:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Edu Collaboration Network
tryCatch(
  {
    log_message("Generating Affliliation Collaboration Network.", "INFO", log_file)
    net_matrix_universities <- biblioNetwork(bibliometrics_data$M,
      analysis = "collaboration",
      network = "universities", sep = ";"
    )
    net_universities <- networkPlot(net_matrix_universities,
      normalize = "association",
      n = 50, Title = "Affiliation Collaboration",
      type = "fruchterman",
      cluster = "louvain",
      size.cex = TRUE, edgesize = 2, labelsize = 0.75,
      noloops = TRUE,
      halo = FALSE, curved = TRUE,
      label.color = TRUE,
      community.repulsion = 0.0075
    )
    save_network_plot(net_universities, "affliliation_collaboration_network_top50.png", path_save, log_file)
  },
  error = function(e) {
    log_message(paste("Error in Affliliation Collaboration Network:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Country Collaboration Network
tryCatch(
  {
    log_message("Generating Country Collaboration Network.", "INFO", log_file)
    meta_tags <- metaTagExtraction(bibliometrics_data$M, Field = "AU_CO", sep = ";")
    net_matrix_countries <- biblioNetwork(meta_tags, analysis = "collaboration", network = "countries", sep = ";")
    net_countries <- networkPlot(net_matrix_countries,
      n = 50,
      Title = "Country Collaboration",
      type = "circle",
      size = TRUE,
      remove.multiple = FALSE,
      labelsize = 0.8
    )
    save_network_plot(net_countries, "country_collaboration_network_top50.png", path_save, log_file)
  },
  error = function(e) {
    log_message(paste("Error in Country Collaboration Network:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Thematic Map
tryCatch(
  {
    log_message("Generating Thematic Map.", "INFO", log_file)
    thematic_map_results <- thematicMap(bibliometrics_data$M,
      field = "ID", n = 1000, minfreq = 2,
      stemming = FALSE, size = 0.25,
      n.labels = 6, repel = TRUE
    )
    thematic_map_plot <- plot(thematic_map_results$map)
    # Since plot() generates output on screen, save the image using dev.copy
    png(file.path(path_save, "thematic_map_6labels.png"), width = 800, height = 600)
    plot(thematic_map_results$map)
    dev.off()
    log_message(paste("Thematic map saved in:", file.path(path_save, "thematic_map_6labels.png")), "INFO", log_file)
  },
  error = function(e) {
    log_message(paste("Error in Thematic Map:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Conceptual Structure using keywords (MCA)
tryCatch(
  {
    log_message("Generating Conceptual Structure (MCA) plot.", "INFO", log_file)
    suppressWarnings({
      conceptual_structure <- conceptualStructure(bibliometrics_data$M,
        method = "MCA",
        field = "ID",
        minDegree = 5,
        clust = 5,
        stemming = FALSE,
        labelsize = 10,
        documents = 100
      )

      # Save plot of terms
      save_plot(conceptual_structure$graph_terms,
        "conceptual_structure_terms_MAC_5cluster.png",
        width = 10,
        height = 8
      )

      # Save plot of documents with highest contributions
      save_plot(conceptual_structure$graph_documents_Contrib,
        "conceptual_structure_docs_contrib_MAC_5cluster.png",
        width = 10,
        height = 8
      )

      # Save plot of most cited documents
      save_plot(conceptual_structure$graph_documents_TC,
        "conceptual_structure_docs_tc_MAC_5cluster.png",
        width = 10,
        height = 8
      )

      # Save dendrogram
      png(file.path(path_save, "conceptual_structure_dendogram.png"),
        width = 3000, height = 2400, res = 300
      )
      plot(conceptual_structure$graph_dendogram)
      log_message("Dendrogram saved successfully.", "INFO", log_file)
    })
  },
  error = function(e) {
    log_message(paste("Error in Conceptual Structure:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Historical Citation Network
tryCatch(
  {
    log_message("Generating Historical Citation Network.", "INFO", log_file)
    historical_results <- histNetwork(bibliometrics_data$M, sep = ";")
    hist_plot <- histPlot(
      historical_results,
      n = 50,
      labelsize = 4,
      size = 4,
      label = "short",
      verbose = FALSE
    )

    # Save the ggraph plot object
    png(
      file.path(path_save, "historical_citation_network_top50.png"),
      width = 3000,
      height = 2400,
      res = 300
    )
    print(hist_plot$g)
    log_message("Historical Citation Network saved successfully.", "INFO", log_file)
  },
  error = function(e) {
    err_msg <- paste("Error in Historical Citation Network:", e$message)
    log_message(err_msg, "ERROR", error_log_file)
  }
)


# Plot: Coupling map - Cited References
tryCatch(
  {
    log_message("Generating Coupling Map Cited References", "INFO", log_file)
    coupling_map_cr <- couplingMap(
      bibliometrics_data$M,
      analysis = "documents",
      field = "CR",
      n = 500,
      label.term = NULL,
      ngrams = 1,
      impact.measure = "local",
      minfreq = 5,
      community.repulsion = 0.1,
      stemming = FALSE,
      size = 0.5,
      n.labels = 1,
      repel = TRUE,
      cluster = "walktrap"
    )

    # Save the plot using ggsave since coupling_map_cr$map is a ggplot object
    coupling_cr_filename <- file.path(
      path_save,
      "coupling_map_cited_ref_fre5_top500.png"
    )

    # Use the actual ggplot object from the results
    ggsave(
      filename = coupling_cr_filename,
      plot = coupling_map_cr$map,
      width = 10,
      height = 8,
      dpi = 300
    )

    log_message(
      paste("Coupling Map (CR) saved in:", basename(coupling_cr_filename)),
      "INFO",
      log_file
    )
  },
  error = function(e) {
    log_message(
      paste("Error in Coupling Map (CR):", e$message),
      "ERROR",
      error_log_file
    )
  }
)


# Plot: Keyword Growth
tryCatch(
  {
    log_message("Generating Keyword Growth plot.", "INFO", log_file)
    keyword_growth <- KeywordGrowth(bibliometrics_data$M, Tag = "ID", sep = ";", top = 20, cdf = TRUE)
    df_keyword_growth <- melt(keyword_growth, id.vars = "Year", variable.name = "Keyword", value.name = "Count")
    plot_keyword_growth <- ggplot(df_keyword_growth, aes(x = Year, y = Count, color = Keyword, group = Keyword)) +
      geom_line(size = 1) +
      geom_point(size = 3) +
      theme_bw() +
      labs(title = "Keyword Growth Over Time", x = "Year", y = "Cumulative Count") +
      theme(legend.position = "bottom", legend.title = element_blank()) +
      scale_color_brewer(palette = "Set1")
    save_plot(plot_keyword_growth, "keyword_growth_top20.png", width = 10, height = 8)
  },
  error = function(e) {
    log_message(paste("Error in Keyword Growth:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Journal Publication (Source Growth)
tryCatch(
  {
    log_message("Generating Journal Publication Growth plot.", "INFO", log_file)
    source_growth <- sourceGrowth(bibliometrics_data$M, top = 5, cdf = TRUE)
    df_source_growth <- as.data.frame(source_growth)
    df_source_growth$Year <- rownames(df_source_growth)
    df_source_long <- melt(df_source_growth, id.vars = "Year", variable.name = "Journal", value.name = "Count")
    plot_source_growth <- ggplot(df_source_long, aes(x = Year, y = Count, color = Journal, group = Journal)) +
      geom_line(size = 1) +
      geom_point(size = 3) +
      theme_bw() +
      labs(title = "Journal Publication Growth Over Time", x = "Year", y = "Cumulative Count") +
      theme(legend.position = "bottom", legend.title = element_blank(), legend.text = element_text(size = 8)) +
      scale_color_brewer(palette = "Set2")
    save_plot(plot_source_growth, "journal_publication_growth_top5.png", width = 10, height = 8)
  },
  error = function(e) {
    log_message(paste("Error in Journal Publication Growth:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Sankey plot for field connectivity
tryCatch(
  {
    log_message("Generating Sankey plot.", "INFO", log_file)

    # Extract country metadata
    countries_meta <- metaTagExtraction(
      bibliometrics_data$M,
      Field = "AU_UN",
      aff.disamb = TRUE
    )
    # Create the Sankey plot
    sankey_plot <- threeFieldsPlot(
      countries_meta,
      fields = c("ID", "AU_UN", "AU_CO")
    ) %>%
      plotly::add_annotations(
        x = c(0.5),
        y = c(-0.2),
        text = c("Legend: ID = Keywords | AU_UN = University of Affiliation | AU_CO = Country of Affiliation"),
        showarrow = FALSE,
        xanchor = "center",
        font = list(color = "black", size = 12, italic = TRUE)
      ) %>%
      plotly::layout(margin = list(b = 100))

    # Save as HTML file
    sankey_filename <- file.path(path_save, "sankey_plot_ID_AUUN_AUCO.html")
    htmlwidgets::saveWidget(
      sankey_plot,
      file = sankey_filename,
      selfcontained = TRUE
    )

    log_message("Sankey plot saved as HTML", "INFO", log_file)
  },
  error = function(e) {
    log_message(
      paste("Error generating Sankey plot:", e$message),
      "ERROR",
      error_log_file
    )
  }
)


# Plot: Top 20 keywords per year with stacked bar chart
tryCatch(
  {
    log_message("Generating Top 20 keywords per year analysis.", "INFO", log_file)

    # Using directly M data frame with ID and publication_date columns
    M_data <- bibliometrics_data$M

    # Extract year from publication_date
    M_data$Year <- as.numeric(substr(M_data$PY, 1, 4))

    # Calculate the last 10 years range
    current_year <- as.numeric(format(Sys.Date(), "%Y"))
    last_10_years <- (current_year - 9):current_year

    # Create a data frame with keywords counts by year
    yearly_keywords <- data.frame(Year = integer(), Keyword = character(), Count = integer())

    # For each document, extract keywords and add to the yearly_keywords data frame
    for (i in 1:nrow(M_data)) {
      year <- M_data$Year[i]
      if (!is.na(year) && year %in% last_10_years) { # Only include last 10 years
        # Get keywords for current document
        keywords_string <- M_data$ID[i]

        if (!is.na(keywords_string) && keywords_string != "") {
          # Split keywords by separator
          keywords <- unlist(strsplit(keywords_string, ";"))
          keywords <- trimws(keywords) # Remove leading/trailing whitespace

          if (length(keywords) > 0) {
            # Create a dataframe for current document's keywords
            doc_df <- data.frame(
              Year = rep(year, length(keywords)),
              Keyword = keywords,
              Count = 1
            )

            # Append to the main dataframe
            yearly_keywords <- rbind(yearly_keywords, doc_df)
          }
        }
      }
    }

    # If we have keywords data, proceed with aggregation
    if (nrow(yearly_keywords) > 0) {
      # Aggregate to get total count per keyword per year
      yearly_keywords_agg <- aggregate(Count ~ Year + Keyword, data = yearly_keywords, FUN = sum)

      # Get the top 20 keywords across all years
      top_keywords_df <- aggregate(Count ~ Keyword, data = yearly_keywords_agg, FUN = sum)
      top_keywords_df <- top_keywords_df[order(top_keywords_df$Count, decreasing = TRUE), ]
      top_keywords <- top_keywords_df$Keyword[1:min(20, nrow(top_keywords_df))]

      # Filter the data to include only the top 20 keywords
      filtered_keywords <- yearly_keywords_agg[yearly_keywords_agg$Keyword %in% top_keywords, ]

      # Create a wide format dataframe for Excel
      keywords_wide <- reshape(filtered_keywords,
        idvar = "Keyword",
        timevar = "Year",
        direction = "wide"
      )

      # Rename columns to remove "Count." prefix
      colnames(keywords_wide) <- gsub("Count\\.", "", colnames(keywords_wide))

      # Replace NA with 0
      keywords_wide[is.na(keywords_wide)] <- 0

      # Save to Excel
      excel_file <- file.path(path_save, "top20_keywords_by_year.xlsx")
      write.xlsx(keywords_wide, excel_file)
      log_message("Top 20 keywords by year saved to Excel.", "INFO", log_file)

      # Reorder factors for plotting so most frequent keywords appear at the bottom
      filtered_keywords$Keyword <- factor(
        filtered_keywords$Keyword,
        levels = rev(top_keywords)
      )

      # Create stacked bar chart with more contrasting colors
      stacked_plot <- ggplot(filtered_keywords, aes(x = as.factor(Year), y = Count, fill = Keyword)) +
        geom_bar(stat = "identity", position = "stack") +
        scale_fill_viridis_d(option = "turbo") + # More contrasting color palette
        theme_minimal() +
        labs(
          title = "Top 20 Keywords Distribution (Last 10 Years)",
          x = "Year",
          y = "Keyword Count",
          fill = "Keywords"
        ) +
        theme(
          legend.position = "right",
          axis.text.x = element_text(angle = 45, hjust = 1),
          plot.title = element_text(size = 14, face = "bold"),
          legend.text = element_text(size = 8),
          panel.grid.major.x = element_blank(),
          panel.border = element_rect(fill = NA, color = "gray80")
        )

      save_plot(stacked_plot, "top20_keywords_last_10years.png", width = 12, height = 8)
      log_message("Stacked bar chart of top 20 keywords for last 10 years created.", "INFO", log_file)
    } else {
      log_message("No keyword data found for the last 10 years.", "WARNING", log_file)
    }
  },
  error = function(e) {
    log_message(paste("Error in Keywords analysis:", e$message), "ERROR", error_log_file)
  }
)




# Plot: World Map of Publications by Country
tryCatch(
  {
    log_message("Generating World Map of Publications by Country.", "INFO", log_file)

    # Extract countries list and convert to data frame
    countries_list <- bibliometrics_data[["res"]][["Countries"]]
    df_countries <- data.frame(
      country = names(countries_list),
      publications = as.numeric(countries_list),
      stringsAsFactors = FALSE
    )

    # Convert country names to lowercase for better matching
    df_countries$country <- tolower(df_countries$country)

    # Get top 20 countries by publications
    df_countries <- df_countries[order(df_countries$publications, decreasing = TRUE), ]
    top_20_countries <- df_countries[1:20, ]

    # Save countries data to Excel
    excel_file_countries <- file.path(path_save, "countries_publications_top20.xlsx")
    write.xlsx(top_20_countries, excel_file_countries, rowNames = FALSE)
    log_message("Top 20 countries publications data saved to Excel.", "INFO", log_file)

    # Get world map data
    world_map <- map_data("world")

    # Convert map regions to lowercase for matching
    world_map$region <- tolower(world_map$region)

    # Merge map data with publication data
    world_map_merged <- merge(world_map, top_20_countries,
      by.x = "region",
      by.y = "country",
      all.x = TRUE
    )
    world_map_merged$publications[is.na(world_map_merged$publications)] <- 0
    world_map_merged <- world_map_merged[order(world_map_merged$order), ]

    # Calculate centroid for each country for label placement
    country_centroids <- aggregate(
      cbind(long, lat) ~ region,
      data = world_map_merged,
      FUN = function(x) mean(range(x))
    )

    # Add publications count to centroids
    country_centroids <- merge(
      country_centroids,
      top_20_countries,
      by.x = "region",
      by.y = "country",
      all.x = TRUE
    )

    # Generate world map plot with labels
    map_plot <- ggplot(world_map_merged, aes(x = long, y = lat, group = group)) +
      geom_polygon(aes(fill = publications), color = "darkgray", size = 0.2) +
      geom_text(
        data = country_centroids[!is.na(country_centroids$publications), ],
        aes(
          x = long,
          y = lat,
          label = paste0(toupper(region), "\n(", publications, ")"),
          group = NULL
        ),
        size = 2.5,
        fontface = "bold",
        check_overlap = TRUE
      ) +
      scale_fill_gradient(
        low = "#FFFFFF",
        high = "#0066CC",
        name = "Number of\nPublications"
      ) +
      labs(
        title = "World Map of Publications by Country",
        subtitle = paste("Top ", nrow(top_20_countries))
      ) +
      theme_minimal() +
      theme(
        plot.title = element_text(hjust = 0.5, size = 16),
        plot.subtitle = element_text(hjust = 0.5, size = 12),
        legend.position = "right",
        axis.title = element_blank(),
        axis.text = element_blank(),
        axis.ticks = element_blank()
      )

    # Save the plot
    save_plot(map_plot, "world_map_publications_top20.png", width = 12, height = 8)
    log_message("World map of publications (Top 20) generated successfully.", "INFO", log_file)
  },
  error = function(e) {
    log_message(paste("Error generating World Map of Publications:", e$message), "ERROR", error_log_file)
  }
)


# Plot: Word Cloud of Keywords
tryCatch(
  {
    log_message("Generating Word Cloud of Keywords.", "INFO", log_file)

    # Prepare data for visualizations
    word_freq <- aggregate(Count ~ Keyword, data = yearly_keywords_agg, FUN = sum)
    word_freq <- word_freq[order(word_freq$Count, decreasing = TRUE), ]
    colnames(word_freq) <- c("word", "freq") # Rename columns for wordcloud2

    # Create interactive word cloud
    wc <- wordcloud2(
      word_freq,
      size = 1,
      minSize = 0.5,
      backgroundColor = "white",
      rotateRatio = 0.35,
      shape = "circle",
      color = "random-dark"
    )

    # Save as HTML widget
    saveWidget(
      wc,
      file = file.path(path_save, "keywords_wordcloud.html"),
      selfcontained = TRUE
    )

    log_message("Word cloud visualization saved as HTML successfully.", "INFO", log_file)
  },
  error = function(e) {
    log_message(
      paste("Error in Word Cloud generation:", e$message),
      "ERROR",
      error_log_file
    )
  }
)

# Plot: Treemap of Keywords
tryCatch(
  {
    log_message("Generating Treemap of Keywords.", "INFO", log_file)

    # Prepare data if not already prepared in the word cloud section
    if (!exists("word_freq")) {
      word_freq <- aggregate(Count ~ Keyword,
        data = yearly_keywords_agg,
        FUN = sum
      )
      word_freq <- word_freq[order(word_freq$Count, decreasing = TRUE), ]
      colnames(word_freq) <- c("word", "freq")
    }

    # Check if we have data to create the treemap
    if (nrow(word_freq) > 0) {
      # Get top 50 keywords for treemap
      top_50_keywords <- head(word_freq, min(50, nrow(word_freq)))

      # Prepare data for plotly treemap if plotly is available
      if (require("plotly", quietly = TRUE)) {
        treemap_plot <- plot_ly(
          data = top_50_keywords,
          type = "treemap",
          labels = ~word,
          parents = rep("", nrow(top_50_keywords)),
          values = ~freq,
          textinfo = "label+value+percent parent",
          marker = list(
            colorscale = list(
              c(0.0, "rgb(235,245,255)"), # Lightest blue
              c(0.1, "rgb(220,237,255)"),
              c(0.2, "rgb(185,215,255)"),
              c(0.3, "rgb(150,192,255)"),
              c(0.4, "rgb(114,168,255)"),
              c(0.5, "rgb(79,144,244)"),
              c(0.6, "rgb(64,125,217)"),
              c(0.7, "rgb(50,105,190)"),
              c(0.8, "rgb(36,86,162)"),
              c(0.9, "rgb(22,67,135)"),
              c(1.0, "rgb(8,48,107)") # Darkest blue
            ),
            showscale = TRUE
          ),
          hovertemplate = "<b>%{label}</b><br>Count: %{value}<br><extra></extra>"
        ) %>%
          layout(
            title = "Top 50 Keywords Treemap"
          )

        # Save the interactive plotly treemap
        html_path <- file.path(path_save, "keywords_treemap_top50.html")
        saveWidget(
          as_widget(treemap_plot),
          file = html_path,
          selfcontained = TRUE
        )
        log_message("Interactive treemap HTML saved successfully.", "INFO", log_file)
      }
    } else {
      log_message("No keyword data available to create treemap.", "WARNING", log_file)
    }
  },
  error = function(e) {
    log_message(
      paste("Error in Treemap generation:", e$message),
      "ERROR",
      error_log_file
    )
  }
)


# Plot: Most Cited Papers
tryCatch(
  {
    log_message("Generating Most Cited Papers graph.", "INFO", log_file)

    # Get the most cited papers data
    most_cited <- bibliometrics_data[["res"]][["MostCitedPapers"]]

    # Convert TC to numeric if it's not already
    most_cited$TC <- as.numeric(most_cited$TC)
    most_cited$TCperYear <- as.numeric(most_cited$TCperYear)

    # Sort by TC descending and get top 20
    most_cited <- most_cited[order(-most_cited$TC), ]
    top20_cited <- head(most_cited, 20)

    # Save dataframe of top 20 most cited papers to Excel
    write.xlsx(top20_cited, file.path(path_save, "top20_most_cited_papers.xlsx"))
    log_message("Top 20 most cited papers data saved to Excel.", "INFO", log_file)

    # Create abbreviated paper labels for the plot
    top20_cited$ShortPaper <- substring(top20_cited$Paper, 1, 50)
    top20_cited$ShortPaper <- paste0(top20_cited$ShortPaper, "...")

    # Reorder factor levels so highest TC appears at top
    top20_cited$ShortPaper <- factor(top20_cited$ShortPaper,
      levels = rev(top20_cited$ShortPaper)
    )

    # Calculate appropriate secondary axis scaling factor
    tc_max <- max(top20_cited$TC)
    tc_per_year_max <- max(top20_cited$TCperYear)
    scale_factor <- tc_max / tc_per_year_max

    # Create the plot with dual axes
    p <- ggplot(top20_cited) +
      # Main bars for Total Citations
      geom_bar(aes(y = ShortPaper, x = TC, fill = "Total Citations"),
        stat = "identity", alpha = 0.7
      ) +
      # Add text labels for Total Citations
      geom_text(
        aes(
          y = ShortPaper, x = TC,
          label = TC
        ),
        size = 3, hjust = -0.2, color = "black"
      ) +
      # Add a thin line connecting to Citations per Year points
      geom_segment(
        aes(
          y = ShortPaper, yend = ShortPaper,
          x = 0, xend = TCperYear * scale_factor,
          color = "Citations per Year"
        ),
        linewidth = 0.5, alpha = 0.5
      ) +
      # Add a point for Citations per Year on secondary axis
      geom_point(aes(y = ShortPaper, x = TCperYear * scale_factor, color = "Citations per Year"),
        size = 3
      ) +
      # Add text labels for Citations per Year
      geom_text(
        aes(
          y = ShortPaper, x = TCperYear * scale_factor,
          label = round(TCperYear, 1)
        ),
        size = 3, hjust = -0.2, vjust = -0.5, color = "#CC3333"
      ) +
      # Define colors
      scale_fill_manual(values = c("Total Citations" = "#3366CC")) +
      scale_color_manual(values = c("Citations per Year" = "#CC3333")) +
      # Create dual axes with appropriate labels
      scale_x_continuous(
        name = "Total Citations (TC)",
        sec.axis = sec_axis(~ . / scale_factor, name = "Citations per Year")
      ) +
      labs(
        title = "Top 20 Most Cited Papers",
        y = "Papers"
      ) +
      theme_bw() +
      theme(
        axis.text.y = element_text(size = 8),
        axis.text.x = element_text(size = 9),
        axis.title.y = element_text(face = "bold", size = 10, color = "#333333"),
        axis.title.x = element_text(face = "bold", size = 10, color = "#3366CC"), # Blue color for primary axis
        axis.title.x.top = element_text(face = "bold", size = 10, color = "#CC3333"), # Red color for secondary axis
        axis.text.x.top = element_text(color = "#CC3333"), # Red color for secondary axis text
        axis.text.x.bottom = element_text(color = "#3366CC"), # Blue color for primary axis text
        axis.ticks.x.top = element_line(color = "#CC3333"), # Red color for secondary axis ticks
        axis.ticks.x.bottom = element_line(color = "#3366CC"), # Blue color for primary axis ticks
        legend.position = "bottom",
        legend.title = element_text(face = "bold"),
        legend.text = element_text(size = 9),
        panel.grid.major.y = element_blank(),
        plot.title = element_text(hjust = 0.5, size = 14, face = "bold")
      ) +
      # Combined legend for both metrics
      guides(
        fill = guide_legend(title = NULL),
        color = guide_legend(title = NULL)
      )

    # Save the plot
    save_plot(p, "top20_most_cited_papers.png", width = 14, height = 10)
    log_message("Most cited papers graph with dual axes generated successfully.", "INFO", log_file)
  },
  error = function(e) {
    log_message(paste("Error in Most Cited Papers graph:", e$message), "ERROR", error_log_file)
  }
)

# Plot: Most Locally Cited Papers
tryCatch(
  {
    log_message("Generating Most Locally Cited Papers graph.", "INFO", log_file)

    # Calculate local citations
    local_cit <- localCitations(bibliometrics_data$M, fast.search = FALSE, sep = ";", verbose = FALSE)

    # Extract the papers data
    locally_cited_papers <- local_cit$Papers

    # Sort by LCS (Local Citation Score) descending and get top 20
    locally_cited_papers <- locally_cited_papers[order(-locally_cited_papers$LCS), ]
    top20_locally_cited <- head(locally_cited_papers, 20)

    # Save dataframe of top 20 most locally cited papers to Excel (including global citations)
    write.xlsx(top20_locally_cited, file.path(path_save, "top20_most_locally_cited_papers.xlsx"))
    log_message("Top 20 most locally cited papers data saved to Excel.", "INFO", log_file)

    # Create abbreviated paper labels for the plot
    top20_locally_cited$ShortPaper <- substring(top20_locally_cited$Paper, 1, 50)
    top20_locally_cited$ShortPaper <- paste0(top20_locally_cited$ShortPaper, "...")

    # Reorder factor levels so highest LCS appears at top
    top20_locally_cited$ShortPaper <- factor(top20_locally_cited$ShortPaper,
      levels = rev(top20_locally_cited$ShortPaper)
    )

    # Create the plot with only local citations (LCS)
    p <- ggplot(top20_locally_cited) +
      # Main bars for Local Citations
      geom_bar(aes(y = ShortPaper, x = LCS, fill = "Local Citations"),
        stat = "identity", alpha = 0.8
      ) +
      # Add text labels for Local Citations
      geom_text(aes(y = ShortPaper, x = LCS, label = LCS),
        size = 3.5, hjust = -0.2, color = "black"
      ) +
      # Define colors
      scale_fill_manual(values = c("Local Citations" = "#990066")) +
      labs(
        title = "Top 20 Most Locally Cited Papers",
        x = "Number of Local Citations",
        y = "Papers"
      ) +
      theme_bw() +
      theme(
        axis.text.y = element_text(size = 8),
        axis.text.x = element_text(size = 9),
        axis.title = element_text(face = "bold"),
        legend.position = "bottom",
        legend.title = element_blank(),
        panel.grid.major.y = element_blank(),
        plot.title = element_text(hjust = 0.5, size = 14, face = "bold")
      )

    # Save the plot
    save_plot(p, "top20_most_locally_cited_papers.png", width = 14, height = 10)
    log_message("Most locally cited papers graph generated successfully.", "INFO", log_file)
  },
  error = function(e) {
    log_message(paste("Error in Most Locally Cited Papers graph:", e$message), "ERROR", error_log_file)
  }
)


# End execution
log_message("Script execution completed successfully.", "INFO", log_file)
