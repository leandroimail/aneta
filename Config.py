#################   CONFIGS   #################
#################   CONFIGS   #################
#################   CONFIGS   #################


#################   CONFIGS   #################

### ----------- Path of Bibs Directory  ----------- ###
# path_directory_bibs = r"/home/leandro/ProjetosLeandro/python/asrl/Example"
path_directory_bibs = r"/Users/leandro.ferreira/Library/CloudStorage/OneDrive-Pessoal/Projects/python/asrl/Sandbox/Data/.bibs"

### ----------- Path and    ----------- ###
### Set path of csv/bib and name of base to scrape Abstract and Keywords.
### Set this variables only you use the Scrap abstract for ACM or SPRINGER
### For ACM you need a .bib file type
### For SPRING you need a .csv file type
# path_ACM = r"C:\Users\leand\OneDrive\Área de Trabalho\RS_DQ\ACM.bib"
# path_SPRINGER = r"C:\Users\leand\OneDrive\Área de Trabalho\RS_DQ\SPRINGER_.csv"
path_ACM = r""
path_SPRINGER = r""

#################   Default Type of Deduplication em Analyses Scritp   #################
# default or fuzzy (fuzzy can spend too much time to process, use only with few records)
type_deduplication = r"default"


### ----------- Parh to inclue and exclude criterius  ----------- ###
path_include_file = r"./IncludeExclude/Incluede_Title.txt"
#path_include_file = "./IncludeExclude/Incluede_Title.txt"

path_exlude_file = r"./IncludeExclude/Exclude_Words.txt"
# path_exlude_file = "./IncludeExclude/Exclude_Words.txt"

path_exlude_manual_file = r"./IncludeExclude/Exlude_Manually.txt"
#path_exlude_manual_file = "./IncludeExclude/Exlude_Manually.txt"



### ----------- Regex Expression for criterial include/exclude  ----------- ###
regex_expression_include = ""
regex_expression_exclude = ""





### ----------- Define Conditional Includes and Exclude  ----------- ###


def condition_include(keywords, abstract, title, jcr, scimago, year, type_publication, publication):
    """ condition can be changed using the input terms (keywords, abstract, title)
    
    Condition must return at least one true condition. If at least one condition is true the Bib will be
     selected.
    
    :param keywords: term containing string with keywords split for semicolon
    :param abstract: term containing string with abstract of publication
    :param title: term containing string with title of publication
    :param jcr: term containing float value. Initial in 0
    :param scimago: term containing float value. Initial in 0
    :param year: term containing containing int value with a date(year) of publication
    :param type_publication: term containing string type of publication. Ex: proceedings, article, book
    :param publication: term containing string with name of publication. Can be the name of proceedings, article, book, etc

    :return: this condition return a Boolean term for bool_conditional
    """

    # bool_general = (
    #     (
    #         "lambda" in abstract.lower() or
    #         "kappa" in abstract.lower() or
    #         "streaming" in abstract.lower() or
    #         "dataflow model" in abstract.lower() or
    #         "architecture for iot" in abstract.lower()
    #     ) 
    # )

    # return bool_general
    


##### OPTIONAL FUNCTION ########################
def condition_exclude(keywords, abstract, title, jcr, scimago, year, type_publication, publication):
    """ condition can be changed using the input terms (keywords, abstract, title)

    Condition must return at least one true condition. If at least one condition is true the Bib will be
     not selected.

    :param keywords: terme containing string with keywords split for semicolon
    :param abstract: terme containing string with abstract of publication
    :param title: terme containing string with title of publication
    :param jcr: terme containing float value. Initial in 0
    :param scimago: terme containing float value. Initial in 0
    :param year: terme containing containing int value with a date(year) of publication
    :param type_publication: terme containing string type of publication. Ex: proceedings, article, book
    :param publication: terme containing string with name of publication. Can be the name of proceedings, article, book, etc

    :return: this condition return a Boolean term for bool_conditional
    """
    bool_general = False

    return bool_general


def condition_include(keywords, abstract, title, jcr, scimago, year, type_publication, publication):
    """ condition can be changed using the input terms (keywords, abstract, title)
    
    Condition must return at least one true condition. If at least one condition is true the Bib will be
     selected.
    
    :param keywords: terme containing string with keywords split for semicolon
    :param abstract: terme containing string with abstract of publication
    :param title: terme containing string with title of publication
    :param jcr: terme containing float value. Initial in 0
    :param scimago: terme containing float value. Initial in 0
    :param year: terme containing containing int value with a date(year) of publication
    :param type_publication: terme containing string type of publication. Ex: proceedings, article, book
    :param publication: terme containing string with name of publication. Can be the name of proceedings, article, book, etc

    :return: this condition return a Boolean term for bool_conditional
    """

    bool_general = (
        (
            ("schema matching" in keywords.lower()  or
            "schema matching" in abstract.lower()  or
            "schema matching" in title.lower())

        )
        and
        (
            ("llm" in keywords.lower()  or
            "llm" in abstract.lower()  or
            "llm" in title.lower())
            or

            ("language model" in keywords.lower()  or
            "language model" in abstract.lower()  or
            "language model" in title.lower())
            or

            ("generative ai" in keywords.lower()  or
            "generative ai" in abstract.lower()  or
            "generative ai" in title.lower())
            or

            ("genai" in keywords.lower()  or
            "genai" in abstract.lower()  or
            "genai" in title.lower())
            or

            ("rag" in keywords.lower()  or
            "rag" in abstract.lower()  or
            "rag" in title.lower())
            or

            ("retrieval-augmented generation" in keywords.lower()  or
            "retrieval-augmented generation" in abstract.lower()  or
            "retrieval-augmented generation" in title.lower())
            or

            ("retrieval augmented generation" in keywords.lower()  or
            "retrieval augmented generation" in abstract.lower()  or
            "retrieval augmented generation" in title.lower())
        )        
    )

    return bool_general

#####################  SYSTEM CONFIG #####################
#####################  SYSTEM CONFIG #####################
#####################  SYSTEM CONFIG #####################


##################### DO NOT CHANGE THIS POINT DOWN, UNLESS YOU KNOW AND BE SURE WHAT YOU WILL DO  ####################
##################### DO NOT CHANGE THIS POINT DOWN, UNLESS YOU KNOW AND BE SURE WHAT YOU WILL DO  ####################
##################### DO NOT CHANGE THIS POINT DOWN, UNLESS YOU KNOW AND BE SURE WHAT YOU WILL DO  ####################
##################### DO NOT CHANGE THIS POINT DOWN, UNLESS YOU KNOW AND BE SURE WHAT YOU WILL DO  ####################
##################### DO NOT CHANGE THIS POINT DOWN, UNLESS YOU KNOW AND BE SURE WHAT YOU WILL DO  ####################


###### formate backslash for slash #######
path_directory_bibs = path_directory_bibs.replace("\\","/").strip()
path_ACM = path_ACM.replace("\\","/").strip()
path_SPRINGER = path_SPRINGER.replace("\\","/").strip()
path_include_file = path_include_file.replace("\\","/").strip()
path_exlude_file = path_exlude_file.replace("\\","/").strip()
path_exlude_manual_file = path_exlude_manual_file.replace("\\","/").strip()


#################   path JCR   #################
path_jcr = r"./ImpactFiles/jcr.csv"
path_scimago = r"./ImpactFiles/scimago.csv"

path_impact_factor = [path_jcr, path_scimago]


### ----------- Dictonarys used in scrape Abstrac and Key Words   ----------- ###
json_base = {"ACM" : "ACM",
             "SPRINGER" : "SPRINGER"}

json_url = {"ACM" : "link",
             "SPRINGER" : "URL"}

json_ENTRYTYPE = {"ACM" : "ENTRYTYPE",
             "SPRINGER" : "Content Type"}

json_ID = {"ACM" : ["ID"],
             "SPRINGER" : ["Publication Year", "Item DOI"]}

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
list_type_publication = ["ENTRYTYPE", "type", "Type", "TYPE", "Content Type", "content type", "CONTENT TYPE", 
                        "Publication Type", "publication type", "PUBLICATION TYPE"]
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
