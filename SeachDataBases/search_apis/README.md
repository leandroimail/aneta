# ArXiv Query Application

A Python application for querying arXiv articles and saving results in BibTeX format.

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Create a JSON configuration file (see sample_config.json for example)
2. Run the application:
```bash
python -m arxiv_query_app path/to/config.json
```

## Configuration Options

The JSON configuration file supports the following fields:

- `keywords`: Semicolon-separated list of keywords
- `abstract`: Abstract text to search for
- `title`: Title text to search for  
- `year`: Publication year
- `type_publication`: arXiv category (e.g. cs.LG)
- `publication`: Publication name
- `path_save_research`: Output file path (optional)

## Example

```bash
python -m arxiv_query_app sample_config.json
```

This will search for articles matching the criteria in sample_config.json and save results to research_output/sample_results.bib
