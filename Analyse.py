from difflib import SequenceMatcher as seq_math
from array import array
from statistics import mean
from collections import Counter, OrderedDict
import re
import os
import shutil
import pandas as pd

from time import sleep

from Config import list_abstract, list_title, list_keywords, list_author, list_year, list_publication, list_issn
from Config import condition_include, condition_exclude, path_exlude_file, path_include_file, path_directory_bibs
from Config import path_jcr, path_scimago, path_exlude_manual_file, list_of_fiels_exlude, list_of_fiels_include
from Config import regex_expression_include, list_of_fiels_regex_include, regex_expression_exclude, list_of_fiels_regex_include
from BibTex import join_bib, write_bibtex, bibtex_to_csv


def loop_json(list_dic, bib):
    value = ""

    for key in list_dic:
        if key in bib:
            value += bib[key] + ";"
            value.strip()
            bib.pop(key)

    return value.strip(";")


def create_folder(path):

    path_exit = path + "/OUTPUTS/"
    if os.path.exists(path_exit):
        shutil.rmtree(path_exit)
    os.makedirs(path_exit)


def read_impact_factor(path_impact_factor):
    df_impact = pd.read_csv(path_impact_factor, usecols=[1,2,3,5])
    df_impact.rename(columns={'Rank': 'rank',
                           'Full Journal Title': 'title',
                           'Abbreviated Title' : 'abbreviated',
                           'ISSN' : 'issn',
                           'Journal Impact Factor' : 'jcr'}, inplace=True)

    df_impact.head(50)

    df_impact["title"] = df_impact["title"].str.lower()
    df_impact["title"] = df_impact["title"].map(lambda x: re.sub('[^a-zA-Z0-9 ]', ' ',x))

    df_impact["abbreviated"] = df_impact["abbreviated"].str.lower()
    df_impact["abbreviated"] = df_impact["abbreviated"].map(lambda x: re.sub('[^a-zA-Z0-9 ]', ' ',x))

    df_impact["issn"] = df_impact["issn"].str.lower()
    df_impact["issn"] = df_impact["issn"].map(lambda x: re.sub('[^a-zA-Z0-9]', '',str(x)))

    df_impact.set_index(["title", "abbreviated", "issn"])

    return df_impact


def get_impact_factor(df_impact_factor, title, issn=""):
    jcr_array = array("u")


    if issn:
        jcr_array = df_impact_factor.jcr[df_impact_factor["issn"] == issn].values

    if not any(jcr_array):
        jcr_array = df_impact_factor.jcr[df_impact_factor["title"] == title].values
    elif not any(jcr_array):
        jcr_array = df_impact_factor.jcr[df_impact_factor["abbreviated"] == title].values

    ####ARUMAR ESSA PARTE PORQUEIRA AQUI################
    try:
        return str(jcr_array[0])
    except:
        return None


def standardize_bib(path):
    list_bib = join_bib(path)
    list_return = []

    df_jcr_impact_factor = read_impact_factor(path_jcr)
    df_scimago_impact_factor = read_impact_factor(path_scimago)

    for bibs in list_bib:
        list_new = []
        for bib in bibs:
            abstract = loop_json(list_abstract, bib)
            title = loop_json(list_title, bib)
            keywords = loop_json(list_keywords, bib)
            author = loop_json(list_author, bib)
            year = loop_json(list_year, bib)
            publication = loop_json(list_publication, bib)
            issn = loop_json(list_issn, bib)


            if not issn or issn == 'None':
                issn = ""
            else:
                issn = re.sub('[^a-zA-Z0-9]', '',issn).lower()

            if not abstract or abstract == 'None':
                abstract = ""
            else:
                abstract = abstract.replace("\n", " ").replace("  ", " ").strip()

            if not title or title == 'None':
                title = ""
            else:
                title = title.replace("\n"," ").replace("  ", " ").replace("  ", " ").strip()

            if not keywords or keywords == 'None':
                keywords = ""
            else:
                keywords = keywords.replace(",", ";").replace(" ;", ";").replace("; ", ";")
                keywords = keywords.replace("\n", " ").replace("  ", " ").strip().lower()

            if not author or author == 'None':
                author = ""
            if not year or year == 'None':
                year = ""
            else:
                if len(year) > 4:
                    year = year.replace("/","-")
                    for y in year.split("-"):
                        if len(y) == 4:
                            year = y
                            break
            if not publication or publication == 'None':
                publication = ""

            jcr = ""
            if bib["ENTRYTYPE"] == "article":
                jcr = get_impact_factor(df_jcr_impact_factor,
                                        re.sub('[^a-zA-Z0-9 ]', ' ',publication.lower().strip()),
                                        re.sub('[^a-zA-Z0-9 ]', ' ', issn.lower().strip()))
            if not jcr or jcr == 'None':
                jcr = ""


            scimago = ""
            if bib["ENTRYTYPE"] == "article":
                scimago = get_impact_factor(df_scimago_impact_factor,
                                        re.sub('[^a-zA-Z0-9 ]', ' ',publication.lower().strip()),
                                        re.sub('[^a-zA-Z0-9 ]', ' ', issn.lower().strip()))
            if not scimago or scimago == 'None':
                scimago = ""


            bib["title"] = title.strip()
            bib["keywords"] = keywords
            bib["abstract"] = abstract
            bib["author"] = author
            bib["year"] = year
            bib["publication"] = publication.replace("\n"," ").replace("  ", " ").strip()
            bib["issn"] = issn
            bib["jcr"] = jcr
            bib["scimago"] = scimago

            list_new.append(bib)

        list_return += list_new
    return list_return


# def clean_duplicate(path):
#     bibs = standardize_bib(path)
def clean_duplicate(bibs_clear):
    bibs = list(bibs_clear)
    list_duplicate = []
    list_bib = []

    num = 0

    while len(bibs) > 0:
        bib = bibs[0]
        # print(len(bibs), num)

        duplicate = False
        for ic, bib_c in enumerate(bibs[1: ]):
            ratio_abstract = 0.0
            ratio_title = 0.0
            ratio_keywords = 0.0
            ratio_author = 0.0
            ratio_total = array("f")

            if all((bib["abstract"], bib_c["abstract"])):
                abastract = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib["abstract"].lower()).strip().split())
                abastract_c = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib_c["abstract"].lower()).strip().split())
                ratio_abstract = seq_math(None, abastract, abastract_c).ratio()
                if ratio_abstract > 0.5:
                    ratio_total.append(ratio_abstract)
            if all((bib["title"], bib_c["title"])):
                title = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib["title"].lower()).strip().split())
                title_c = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib_c["title"].lower()).strip().split())
                ratio_title = seq_math(None, title, title_c).ratio()
                if ratio_title > 0.5:
                    ratio_total.append(ratio_title)
            if all((bib["keywords"], bib_c["keywords"])):
                keywords = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib["keywords"].lower()).strip().split())
                keywords_c = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib_c["keywords"].lower()).strip().split())
                ratio_keywords = seq_math(None, keywords, keywords_c).ratio()
                if ratio_keywords > 0.5:
                    ratio_total.append(ratio_keywords)
            if all((bib["author"], bib_c["author"])):
                author = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib["author"].lower()).strip().split())
                author_c = sorted(re.sub('[^a-zA-Z0-9]', ' ', bib_c["author"].lower()).strip().split())
                ratio_author = seq_math(None, author, author_c).ratio()
                if ratio_author > 0.5:
                    ratio_total.append(ratio_author)

            if (ratio_abstract > 0.8 or ratio_title > 0.8 or (len(ratio_total) > 1) and mean(ratio_total) > 0.65):
                duplicate = True
                list_duplicate.append(bib)
                break

        if not duplicate:
            list_bib.append(bib)
        bibs.pop(0)
        num += 1

    write_bibtex(path_directory_bibs + "/OUTPUTS/bib_duplicate.bib", list_duplicate)
    write_bibtex(path_directory_bibs + "/OUTPUTS/bib_deduplicate.bib", list_bib)
    # bibtex_to_csv(path_directory_bibs + "/OUTPUTS/bib_duplicate.bib")
    # bibtex_to_csv(path_directory_bibs + "/OUTPUTS/bib_deduplicate.bib")

    return list_bib, list_duplicate


#################   funções para  critérios de inclusão/exclusão   #################
def process_regex(regex_expression, list_of_fiels_for_regex, bib):
    regex = re.compile(regex_expression)

    for field in list_of_fiels_for_regex:
        if regex.match(bib[field]):
            return True

    return False


def process_list(path_file_include_exclude, list_include_exclude_words, keywords, abstract, title, clean_word=False):
    with open(path_file_include_exclude, 'r', encoding="utf-8") as file:
        list_words = file.readlines()

    if list_include_exclude_words:
        for word in list_words:
            word = word.strip().replace("\n", "").lower()

            if clean_word:
                word = re.sub('[^a-zA-Z0-9] ', '', word)
                word = re.sub('\s+', '', word)

            if ("keywords" in list_include_exclude_words) and (word in keywords.strip().replace("\n", "").lower()):
                return True
            if ("abstract" in list_include_exclude_words) and (word in abstract.strip().replace("\n", "").lower()):
                return True
            if ("title" in list_include_exclude_words) and (word in title.strip().replace("\n", "").lower()):
                return True

    return False


def pre_include(bib):
    keywords = bib["keywords"].lower()
    abstract = bib["abstract"].lower()
    title = bib["title"].lower()

    if condition_include(keywords, abstract, title):
        return True

    if regex_expression_include and list_of_fiels_regex_include:
        if process_regex(regex_expression_include, list_of_fiels_regex_include, bib):
            return True

    if path_include_file and list_of_fiels_include:
        if process_list(path_include_file, list_of_fiels_include, keywords, abstract, title):
            return True

    return False


def pre_exclude(bib):
    keywords = bib["keywords"].lower()
    abstract = bib["abstract"].lower()
    title = bib["title"].lower()

    if condition_exclude(keywords, abstract, title):
        return False

    if regex_expression_exclude and regex_expression_exclude:
        if process_regex(regex_expression_exclude, regex_expression_exclude, bib):
            return False

    if path_exlude_file and list_of_fiels_exlude:
        if process_list(path_exlude_file, list_of_fiels_exlude, keywords, abstract, title):
            return False

    return True


def pre_exclude_sample(bib):
    return not pre_exclude(bib)

def select_final(bib):
    if path_exlude_manual_file:
        title = bib["title"]
        title = re.sub('[^a-zA-Z0-9] ', '', title)
        title = re.sub('\s+', '', title)
        if process_list(path_exlude_manual_file, ["title"], "", "", title, clean_word=True):
            return False
    return True


def display_results(dictionary, name_file, column_key, column_value="value", sort_by_value=False, reverse=False):
    sort_index = 0

    if sort_by_value:
        sort_index = 1

    path = path_directory_bibs + "/OUTPUTS/" + name_file +".csv"
    with open(path, "w") as file:
        file.writelines(column_key + ";" + column_value + "\n" )
        dict_order = OrderedDict(sorted(dictionary.items(), key=lambda t: t[sort_index], reverse=reverse))
        for k, v in dict_order.items():
            print(k.strip("'").strip().strip("\n") + ": " + str(v))

            try:
                file.writelines(k.strip("'").strip().strip("\n") + ";" + str(v).replace(".",",") + "\n")
            except Exception as e:
                print(e)


def summarizer(bibs, bib_duplicate={}):
    count_base = {}
    count_base_type = {}
    count_base_duplicate = {}
    count_year = {}
    count_publication = {}
    count_article = {"article" : 0 , "conference" : 0}
    count_jcr = {}
    count_scimago = {}
    count_keyowrds = {}

    total = 0
    keywords = ""


    for bib in bibs:
        total += 1

        keywords += bib["keywords"].strip().strip("\n")

        if bib["base"] in count_base:
            count_base[bib["base"]] = count_base[bib["base"]] + 1
        else:
            count_base[bib["base"]] = 1
            count_base_type[bib["base"] + "_article" ] = 0
            count_base_type[bib["base"] + "_conference"] = 0


        if bib["ENTRYTYPE"] == "article":
            count_article["article"] = count_article["article"] + 1
            count_base_type[bib["base"] + "_article"] = count_base_type[bib["base"] + "_article" ] + 1
        else:
            count_article["conference"] = count_article["conference"] + 1
            count_base_type[bib["base"] + "_conference"] = count_base_type[bib["base"] + "_conference"] + 1


        if bib["year"] in count_year:
            count_year[bib["year"]] = count_year[bib["year"]] + 1
        else:
            count_year[bib["year"]] = 1

        pub = bib["publication"]
        pub = re.sub('[^a-zA-Z0-9] ', ' ', pub.strip()).lower()
        if pub in count_publication:
            count_publication[pub] = count_publication[pub] + 1
        else:
            count_publication[pub] = 1

        if  bib["jcr"] and bib["jcr"].isnumeric():

            jcr_decimal = round(float(bib["jcr"]), 1)
            if str(jcr_decimal) in count_jcr:
                count_jcr[str(jcr_decimal)] = count_jcr[str(jcr_decimal)] + 1
            else:
                count_jcr[str(jcr_decimal)] = 1

            if "total" in count_jcr:
                count_jcr["total"] = count_jcr["total"] + 1
            else:
                count_jcr["total"] = 1

        if  bib["scimago"]:
            scimago_decimal = round(float(bib["scimago"]), 1)
            if str(scimago_decimal) in count_scimago:
                count_scimago[str(scimago_decimal)] = count_scimago[str(scimago_decimal)] + 1
            else:
                count_scimago[str(scimago_decimal)] = 1

            if "total" in count_scimago:
                count_scimago["total"] = count_scimago["total"] + 1
            else:
                count_scimago["total"] = 1

    dic_aux = {}
    for k, v in count_base.items():
        dic_aux["'percent_" + k] = v / total * 100
    count_base.update(dic_aux)

    dic_aux = {}
    for k, v in count_base_type.items():
        if v:
            dic_aux["'percent_" + k] = v / total * 100
        else:
            dic_aux["'percent_" + k] = 0
    count_base_type.update(dic_aux)

    dic_aux = {}
    for k, v in count_year.items():
        dic_aux["'percent_" + k] = v / total * 100
    count_year.update(dic_aux)

    dic_aux = {}
    for k, v in count_article.items():
        if v:
            dic_aux["'percent_" + k] = v / total * 100
        else:
            dic_aux["'percent_" + k] = 0
    count_article.update(dic_aux)

    dic_aux = {}
    for k, v in count_jcr.items():
        if k != "total":
            dic_aux["'percent_" + k] = v / count_jcr["total"] * 100
    count_jcr.update(dic_aux)


    dic_aux = {}
    for k, v in count_scimago.items():
        if k != "total":
            dic_aux["'percent_" + k] = v / count_scimago["total"] * 100
    count_scimago.update(dic_aux)

    count_base["total"] = total
    count_year["total"] = total
    count_article["total"] = total
    count_keyowrds = dict(Counter(keywords.split(";")))

    if bib_duplicate:

        total = 0
        for bib in bib_duplicate:
            total += 1

            if bib["base"] in count_base_duplicate:
                count_base_duplicate[bib["base"]] = count_base_duplicate[bib["base"]] + 1
            else:
                count_base_duplicate[bib["base"]] = 1

        count_base_duplicate["total"] = total
        dic_aux = {}
        for k, v in count_base_duplicate.items():
            dic_aux["'percent_" + k] = v / total * 100
        count_base_duplicate.update(dic_aux)

    return count_base, count_base_type, count_base_duplicate, count_year, count_publication, count_article, count_jcr, count_scimago, count_keyowrds


def call_results(bibs, bib_duplicate={}, type="select"):
    type = re.sub('[^a-zA-Z0-9]', ' ', type).strip()

    print("Summarizing" + " " + type)
    count_base, count_base_type, count_base_duplicate, count_year, count_publication, count_article, count_jcr, count_scimago, count_keywords = summarizer(bibs, bib_duplicate)

    print("\n")
    print("--- Contagem ---")
    display_results(count_base, type + "_" +"bases", "base")

    print("\n")
    print("--- Contagem Base\Type ---")
    display_results(count_base_type, type + "_" +"base_type", "base_type")

    print("\n")
    print("--- JCR ---")
    display_results(count_jcr, type + "_" + "jcr", "ranges")

    print("\n")
    print("--- SCIMAGO ---")
    display_results(count_scimago, type + "_" + "scimago", "ranges")

    print("\n")
    print("--- Contagem de Anos ---")
    display_results(count_year, type + "_" + "years", "year")

    print("\n")
    print("--- Articles/Conferences ---")
    display_results(count_article, type + "_" + "types_publications", "type")

    if type != "all":

        print("\n\n")
        print("--- Publicações ---")
        display_results(count_publication, type + "_" + "publication", "name")


        print("\n")
        print("--- Count Key Words ---")
        display_results(count_keywords, type + "_" +"keywords_counts", "word", sort_by_value=True, reverse=True)


        if bib_duplicate:
            print("\n")
            print("--- Contagem Duplicate ---")
            display_results(count_base_duplicate, type + "_" + "bases_duplicates", "bases")




def analyzer(path):
    print("Loading and standardize Bibs")
    bibs = standardize_bib(path)
    summary = {}
    include_bib = []
    exclude_bib = []
    bibs_without_exclude = []

    # word_count_keywords(bibs)

    print("Select Includes Bibs")
    include_bib = list(filter(pre_include, bibs))

    print("Exludes Bibs")
    bibs_without_exclude = list(filter(pre_exclude, include_bib))

    print("Get Excludes Bibs")
    exclude_bib = list(filter(pre_exclude_sample, include_bib))

    print("Deduplicate Excludes Bibs")
    exclude_bib_deduplicate, _ = clean_duplicate(exclude_bib)
    write_bibtex(path_directory_bibs + "/OUTPUTS/bib_exclude.bib", exclude_bib_deduplicate)

    print("Deduplicate Include Bibs")
    deduplicate, duplicate = clean_duplicate(bibs_without_exclude)

    summary_bibs = {
        "total_bibs": len(bibs),
        "total_include": len(include_bib),
        "total_exclude": len(exclude_bib),
        "total_exclude_deduplique": len(exclude_bib_deduplicate),
        "bibs_without_exclude": len(bibs_without_exclude),
        "pre_selects": len(deduplicate),
        "duplicates": len(duplicate),


    }

    if len(exclude_bib):
        summary_bibs["'percente_exclude_over_include"] = str(len(exclude_bib) / len(include_bib) * 100) + "%"
    else:
        summary_bibs["'percente_exclude_over_include"] = "0%"

    if len(duplicate):
        summary_bibs["'percente_duplicates"] = str(len(duplicate) / len(include_bib) * 100) + "%"
        summary_bibs["'percente_pre_select"] = str(len(duplicate) / len(bibs) * 100) + "%"
    else:
        summary_bibs["'percente_duplicates"] = "0%"
        summary_bibs["'percente_pre_select"] = "0%"

    if   len(include_bib):
        summary_bibs["'precente_include_over_total"] = str(len(include_bib) / len(bibs) * 100) + "%"
    else:
        summary_bibs["'precente_include_over_total"] = "0%"




    if path_exlude_manual_file:
        print("Select Manual Bibs")
        select_bibs = list(filter(select_final, deduplicate))
        write_bibtex(path_directory_bibs + "/OUTPUTS/select_bibs.bib", select_bibs)
        # bibtex_to_csv(path_directory_bibs + "/OUTPUTS/select_bibs.bib")

        summary_bibs["select"] = len(select_bibs)

        if len(deduplicate):
            summary_bibs["exclude_manually"] = len(deduplicate) - len(select_bibs)
            summary_bibs["percente_selec_over_pre_select"] = str(len(select_bibs) / len(deduplicate) * 100) + "%"
        else:
            summary_bibs["exclude_manually"] = len(select_bibs)
            summary_bibs["percente_selec_over_pre_select"] = "100%"

        call_results(select_bibs, type="select")
        call_results(bibs, type="all")

    call_results(deduplicate, duplicate, type="pre_select")

    print("\n")
    print("---  ---")
    display_results(summary_bibs, "sumary", "resume")


    # print("\n")
    # print("--- Gravando Titles ---")
    # path = path_directory_bibs + "/OUTPUTS/title.csv"
    # with open(path, "w") as file:
    #     for bib in select_bibs:
    #         file.writelines(bib["title"] + "\n")



# clean_duplicate(path_directory_bibs)
create_folder(path_directory_bibs)
analyzer(path_directory_bibs)
