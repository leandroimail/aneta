
from dotenv import load_dotenv
import os

from Config.Deprecated.DeprecatedConfigPythonFile.Config import regex_expression_include as regex_expression_include_deprecated
from Config.Deprecated.DeprecatedConfigPythonFile.Config import regex_expression_exclude as regex_expression_exclude_deprecated
from Config.Deprecated.DeprecatedConfigPythonFile.Config import condition_include as condition_include_deprecated
from Config.Deprecated.DeprecatedConfigPythonFile.Config import condition_exclude as condition_exclude_deprecated

load_dotenv()
load_dotenv(os.path.abspath("Config/.env"))

#####################  SYSTEM CONFIG #####################
#####################  SYSTEM CONFIG #####################
#####################  SYSTEM CONFIG #####################


### ----------- Path of Bibs Directory  ----------- ###


path_directory_bibs = os.path.abspath(os.getenv("PATH_DATA", "Data"))
path_directory_bibs = os.path.join(path_directory_bibs, ".bibs")

### ----------- Path and    ----------- ###
### Set path of csv/bib and name of base to scrape Abstract and Keywords.
### Set this variables only you use the Scrap abstract for ACM or SPRINGER
path_ACM = os.getenv("PATH_ACM", "")
path_SPRINGER = os.getenv("PATH_SPRINGER", "")

if path_ACM:
    path_ACM = os.path.abspath(path_ACM)
if path_SPRINGER:
    path_SPRINGER = os.path.abspath(path_SPRINGER)


#################   Default Type of Deduplication em Analyses Scritp   #################
# default or fuzzy (fuzzy can spend too much time to process, use only with few records)
type_deduplication = os.getenv("TYPE_DEDUPLICATION", "default")


### ----------- Parh to inclue and exclude criterius  ----------- ###
path_include_file = os.getenv("PATH_INCLUDE_FILE", "")
if path_include_file:
    path_include_file = os.path.abspath(path_include_file)

path_exlude_file = os.getenv("PATH_EXLUDE_FILE", "")
if path_exlude_file:
    path_exlude_file = os.path.abspath(path_exlude_file)

path_exlude_manual_file = os.getenv("PATH_EXLUDE_MANUAL_FILE", "")
if path_exlude_manual_file:
    path_exlude_manual_file = os.path.abspath(path_exlude_manual_file)


### ----------- Regex Expression for criterial include/exclude  ----------- ###
regex_expression_include = regex_expression_include_deprecated
regex_expression_exclude = regex_expression_exclude_deprecated


### ----------- Define Conditional Includes and Exclude  ----------- ###
condition_include = condition_include_deprecated
condition_exclude = condition_exclude_deprecated



#################   path JCR   #################
path_jcr = os.getenv("PATH_JCR", "")
if path_jcr:
    path_jcr = os.path.abspath(path_jcr)
path_scimago = os.getenv("PATH_SCIMAGO", "")
if path_scimago:
    path_scimago = os.path.abspath(path_scimago)

path_impact_factor = [path_jcr, path_scimago]

### ----------- Dictonarys used in scrape Abstrac and Key Words   ----------- ###
json_base = {
    "ACM" : "ACM",
    "SPRINGER" : "SPRINGER"
}

json_url = {
    "ACM" : "link",
    "SPRINGER" : "URL"
}

json_ENTRYTYPE = {
    "ACM" : "ENTRYTYPE",
    "SPRINGER" : "Content Type"
}

json_ID = {
    "ACM" : ["ID"],
    "SPRINGER" : ["Publication Year", "Item DOI"]
}

list_type_bibtex = ["article", "book", "booklet", "conference", "inbook", "incollection", "inproceedings", "manual",
                    "mastersthesis", "misc", "phdthesis", "proceedings", "techreport", "unpublished"]


### ----------- Lists of terms to Standardize Bibs  ----------- ###
### Set terms used in Bibs for each field to standardize ###
list_issn = ["issn", "ISSN", "Issn"]
list_doi = ["doi", "Doi", "DOI", "Item DOI"]
list_abstract = ["abstract", "ABSTRACT", "Abstract"]
list_title = ["title", "Title", "TITLE",  "Item Title", "item title"]
list_keywords = ["keyword", "Keyword", "KEYWORD", "Keywords", "keywords", "KEYWORDS", "Keywords-Plus"]
list_author = ["author", "Author", "AUTHOR", "authors", "Authors", "AUTHORS"]
list_year = ["year", "Year", "YEAR", "Publication Year", "publication year", "PUBLICATION YEAR", "Date", "DATE", "date"]
list_publication = ["journal", "Journal", "JOURNAL", "booktitle", "Booktitle", "BOOKTITLE", "Publication Title",
                    "publication title", "PUBLICATION TITLE", "publication","Publication","PUBLICATION", "source", "Source", "SOURCE",
                    "publicationName", "PublicationName", "Publication Name", "publication name", "Publication name", "publicationname"]
list_type_publication = ["ENTRYTYPE", "entrytype", "type", "Type", "TYPE", "Content Type", "content type", "CONTENT TYPE", 
                        "Publication Type", "publication type", "PUBLICATION TYPE", "content_type", "CONTENT_TYPE", "Content Type",
                        "Type Publication", "type publication", "TYPE PUBLICATION", "TypePublication", "type_publication", "TYPE_PUBLICATION",]
list_publisher = ["publisher", "Publisher", "PUBLISHER", "publisherName", "PublisherName", "Publisher Name", "publisher name", "Publisher name", "publishername",
                    "Publisher-Name", "PUBLISHER NAME", "PUBLISHERNAME",]
list_abbreviated_publication = ["abbrev_source_title", "abbrev_source_title", "Abbrev Source Title", "Abbrev Source Title", "Abbrev Source Title",
                                "abbreviated", "Abbreviated", "ABBREVIATED", "Abbreviated Source Title", "abbreviated source title", "Abbreviated Source Title",]


def webdriver ():
    """ Instantiate Selenium webdriver
    ----------------------   Don't Toch ----------------------
    :return: webdrive Selenium instantiated
    """
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager
    return webdriver.Chrome(ChromeDriverManager().install())
