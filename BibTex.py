import csv
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
import os



def read_bibtex(path):
    with open(path, "r", encoding='utf-8') as bibtex_file:
        parser = BibTexParser()
        parser.customization = convert_to_unicode
        bib_database = bibtexparser.load(bibtex_file, parser=parser)

        return bib_database.entries


def write_bibtex(path, entries):
    db = BibDatabase()
    db.entries = entries
    writer = BibTexWriter()
    with open(path, 'w', encoding='utf-8') as bibfile:
        bibfile.write(writer.write(db))


def write_new_bibtex(path, entries):
    arq = path.split("/")[-1]
    path_exit = path.replace(arq, "NEW/")
    if not os.path.exists(path_exit):
        os.makedirs(path_exit)
    path_exit += arq.replace(".csv", "_NEW.bib")
    db = BibDatabase()
    db.entries = entries
    writer = BibTexWriter()
    with open(path_exit, 'w', encoding='utf-8') as bibfile:
        bibfile.write(writer.write(db))


def bibtex_to_csv(path):
    path_exit = path.replace(".bib", ".csv")
    list_bibs = read_bibtex(path)
    fieldnames = []
    for bib in list_bibs:
        if set(fieldnames) != set(bib.keys()):
            fieldnames = list(set(list(bib.keys())+fieldnames))

    with open(path_exit, 'w', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',', quotechar='"',
                                quoting=csv.QUOTE_NONNUMERIC, lineterminator='\n')

        writer.writeheader()
        for bib in list_bibs:
            writer.writerow(bib)

    return path_exit


def deduplicate_bib(path, arq):
    path += "NEW/"
    arq = arq.replace(".bib", "_NEW.bib")

    for caminho, diretorios, arquivo in os.walk(path):
        if arq in arquivo:
            return False

    return True


def join_bib(path):
    def add_base(dic):
        """ função usa cloujere para acessar o arquivo (arq) e adicionar a base de dados pesquisada no bibtex

        :param dic: um dicionario
        :return: retorna o dicionario acrescentando a base de dados pesquisada
        """
        dic["base"] = arq.split(".")[0]
        return dic

    bibs = []
    bib = []

    for caminho, diretorios, arquivos in os.walk(path):
        if arquivos:
            for arq in arquivos:
                if ((".bib" in arq) and (deduplicate_bib(path, arq))):
                    new_path = caminho.strip("/") + "/" + arq
                    print(new_path)
                    bib = read_bibtex(new_path)
                    bib = list(map(add_base, bib))
                    bibs.append(bib)
    return bibs



