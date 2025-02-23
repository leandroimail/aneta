#################   CONFIGS   #################


### ----------- Define Conditional Includes and Exclude  ----------- ###

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
    


################################################      OPTIONAL FUNCTION     ################################################
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


### ----------- Regex Expression for criterial include/exclude  ----------- ###
regex_expression_include = ""
regex_expression_exclude = ""


###############################################################################################################################



