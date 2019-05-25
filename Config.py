##### Backlog #####
#- Ver Problema no Science Direct
#- Classificar pelo Scimago
#- Fazer lista de proximidade
#- Gerar Graficos
#- Verificar a integração da API
#- Gerar relatórios de mostivos com o exclude manual
#- Arrumar a geração de CSV. Campos estão com \n e saem com linha quebras no csv
#- Exclusão por JCR e Simago
#################   CONFIGS   #################


### ----------- Path of Bibs  ----------- ###
path_directory_bibs = r"C:\Users\leand\OneDrive\Área de Trabalho\RS_DQ"
path_directory_bibs = path_directory_bibs.replace("\\","/")


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

### ----------- Path and    ----------- ###
### Set path of csv/bib and name of base to scrape Abstract and Keywords.
### default funcictions for bases Springer and ACM
path_csv = r"C:\Users\leand\OneDrive\Área de Trabalho\RS_DQ\ACM.bib"
path_csv = path_csv.replace("\\","/")
type_base = "ACM"


### ----------- Lists of terms to Standardize Bibs  ----------- ###
### Set terms used in Bibs for each field to standardize ###
list_issn = {"issn", "ISSN", "Issn"}
list_abstract = ["abstract", "ABSTRACT", "Abstract"]
list_title = ["title", "Title", "TITLE",  "Item Title", "item title"]
list_keywords = ["keyword", "Keyword", "KEYWORD", "Keywords", "keywords", "KEYWORDS", "Keywords-Plus"]
list_author = ["author", "Author", "AUTHOR", "authors", "Authors", "AUTHORS"]
list_year = ["year", "Year", "YEAR", "Publication Year", "publication year", "PUBLICATION YEAR", "Date", "DATE",
             "date"]
list_publication = ["journal", "Journal", "JOURNAL", "booktitle", "Booktitle", "BOOKTITLE", "Publication Title",
                    "publication title", "PUBLICATION TITLE"]


### ----------- Parh to inclue and exclude criterius  ----------- ###
path_include_file = "C:/Users/leand/PycharmProjects/RevisaoSistematica/IncludeExclude/Incluede_Title.txt"
list_of_fiels_include = ["title", "keywords", "abstract"]

# path_exlude_file = "./IncludeExclude/Exclude_Words.txt"
path_exlude_file = ""
list_of_fiels_exlude = ["title", "keywords", "abstract"]

#path_exlude_manual_file = ""
path_exlude_manual_file = "./IncludeExclude/Exlude_Manually.txt"

regex_expression_include = ""
list_of_fiels_regex_include = ["title", "keywords", "abstract"]

regex_expression_exclude = ""
list_of_fiels_regex_include = ["title", "keywords", "abstract"]




def condition_exclude(keywords, abstract, title):
    """ condition can be changed using the input terms (keywords, abstract, title)

    Condition must return at least one true condition. If at least one condition is true the Bib will be
     selected.

    :param keywords: terme containing string with keywords split for semicolon
    :param abstract: terme containing string with com o abstract do texto
    :param title: terme containing string with com o abstract do texto
    :return: this condition return a Boolean term for bool_conditional
    """
    bool_general = False

    return bool_general



#################   path JCR   #################
path_jcr = "./ImpactFiles/jcr.csv"
path_scimago = "./ImpactFiles/scimago.csv"

path_impact_factor = [path_jcr, path_scimago]

#################   webdriver   #################
path_webdriver = "C:/Users/leand/PycharmProjects/RevisaoSistematica/webdriver/chromedriver.exe"
path_webdriver = path_webdriver.replace("\\","/")


def webdriver ():
    """ Instantiate Selenium webdriver

    ----------------------   Don't Toch ----------------------

    :return: webdrive Selenium instantiated
    """
    from selenium import webdriver
    return webdriver.Chrome(path_webdriver)




### ----------- Define Conditional Includes and Exclude  ----------- ###
def condition_include(keywords, abstract, title):
    """ condition can be changed using the input terms (keywords, abstract, title)
    
    Condition must return at least one true condition. If at least one condition is true the Bib will be
     selected.
    
    :param keywords: terme containing string with keywords split for semicolon
    :param abstract: terme containing string with com o abstract do texto
    :param title: terme containing string with com o abstract do texto
    :return: this condition return a Boolean term for bool_conditional
    """

    bool_general = (



        ("metadata" in keywords  or
         "metadata" in abstract  or
         "metadata" in title)
        and
        ("data quality" in keywords  or
         "data quality" in abstract  or
         "data quality" in title)
        and
        ("model" in keywords  or
         "model" in abstract  or
         "model" in title)
    )

  #   bool_general = ((("nosql" in keywords)
  #
	#    and
  #
	#    ("data warehouse" in keywords or
 	#     "olap" in keywords or
	#     "multidimensional" in keywords or
	#     "star schema" in keywords))
  # or
  #
  #  (("nosql" in  abstract)
  #
  #    and
  #
	#    ("data warehouse" in abstract or
	#     "olap" in abstract or
	#     "multidimensional" in abstract or
	#     "star schema" in abstract))
  #
  # or
  #
  #  (("nosql" in  title)
  #
  #    and
  #
	#    ("data warehouse" in title or
	#     "olap" in title or
	#     "multidimensional" in title or
	#     "star schema" in title)))


    return bool_general






