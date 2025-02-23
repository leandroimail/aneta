import csv
import time

from bs4 import BeautifulSoup
from BibTex import bibtex_to_csv, write_new_bibtex
from Config import webdriver, json_base, json_url, json_ENTRYTYPE, json_ID, list_type_bibtex

driver = webdriver()


def parse_html(html, type_base):
    if type_base == "ACM":
        return parser_html_acm(html)

    if type_base == "SPRINGER":
        return parser_html_springer(html)


def parser_html_acm(html):
    soup = BeautifulSoup(html, 'html.parser')

    # result = soup.find("div", {"id": "abstract"})
    results = soup.findAll('div', attrs={'style': 'display:inline'})
    for result in results:
        return str(result.p.string), None

    return None, None


def parser_html_springer(html):
    abstract = ""
    keywords = ""
    soup = BeautifulSoup(html, 'html.parser')
    results = soup.findAll(id="Abs1")

    for result in results:
        abstract = result.p.string
        if abstract:
            abstract = abstract.strip("Abstract").strip("abstract")
            break

    if not abstract:
        for result in results:
            abstract = result.text
            if abstract:
                abstract = abstract.strip("Abstract").strip("abstract")
                break

    results = soup.findAll('span', attrs={'class': 'Keyword'})

    for result in results:
        keywords += result.text.strip() + ";"

    return abstract, keywords


def get_html(url, type_base):
    try:
        driver.get(url)
        time.sleep(3)
        html = driver.page_source
        return parse_html(html, type_base)
    except Exception as e:
        print(e)
        return None, None


def insert_id(row, type_base):
    identify = ""
    for item in json_ID[type_base]:
        identify += row[item].replace("/", "_") + ":"
    return identify[:-1]


def get_csv(path, type_base):
    type_base = json_base[type_base]
    if path[-3:].upper() == "CSV":
        return path, type_base

    path = bibtex_to_csv(path)
    return path, type_base


def get_abstract(path, type_base):
    path, type_base = get_csv(path, type_base)
    url_base = json_url[type_base]
    bib_exit = []
    unsusseful = []

    with open(path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')

        # count = 0
        for row in reader:
            url = row[url_base]
            abstract, keywords = get_html(url, type_base)
            entrytype = row[json_ENTRYTYPE[type_base]]

            if entrytype.lower() not in list_type_bibtex:
                entrytype = "misc"

            if not abstract:
                unsusseful.append(row)
            else:
                row["ID"] = insert_id(row, type_base)
                row["ENTRYTYPE"] = entrytype
                row["abstract"] = abstract
                if keywords:
                    row["keywords"] = keywords
                bib_exit.append(row)

        if unsusseful:
            fieldnames = row.keys()
            path_error = path.replace(".csv", "_ERROR.csv")
            with open(path_error, 'w', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',', quotechar='"',
                                        quoting=csv.QUOTE_NONNUMERIC, lineterminator='\n')
                writer.writeheader()

                for row_unsus in unsusseful:
                    url = row_unsus[url_base]
                    abstract, keywords = get_html(url, type_base)
                    entrytype = row[json_ENTRYTYPE[type_base]]

                    if entrytype.lower() not in list_type_bibtex:
                        entrytype = "misc"
                    if not abstract:
                        writer.writerow(row_unsus)
                    else:
                        row_unsus["abstract"] = abstract
                        row_unsus["ID"] = insert_id(row_unsus, type_base)
                        row_unsus["ENTRYTYPE"] = entrytype
                        if keywords:
                            row_unsus["keywords"] = keywords
                        bib_exit.append(row_unsus)
        driver.close()
        write_new_bibtex(path, bib_exit)