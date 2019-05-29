from Config import path_SPRINGER, path_ACM

###################  Informe se deve-se rodar a leitura do abstract
###################  run_abstract seja falso, rodará a Análise dos Bibtex
run_abstract = False


if __name__ == "__main__":
    if run_abstract:
        from Abstract import get_abstract

        if path_SPRINGER:
            get_abstract(path_SPRINGER, "SPRINGER")
        if path_ACM:
            get_abstract(path_ACM, "ACM")

    else:
        from Analyse import get_analyse
        get_analyse()




