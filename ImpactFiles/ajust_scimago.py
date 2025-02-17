import csv


file = "./scimago.csv"

file_new = "./scimago_novo.csv"

new_csv = []
ISSN = []
with open(file, 'r', encoding="utf8") as file:
    csv_file = csv.DictReader(file, delimiter=",", )
    for row in csv_file:
        ISSN = row["ISSN"].split(";")
        if len(ISSN) > 1:
            for unit_issn in ISSN:
                aux = dict(row)
                aux["ISSN"] = unit_issn
                new_csv.append(aux)
        else:
            new_csv.append(row)




with open(file_new, 'w', encoding="utf8") as file:
    fieldnames = ["Rank", "Full Journal Title", "Abbreviated Title", "ISSN", "Total Cites", "Journal Impact Factor"]
    csv_file = csv.DictWriter(file, fieldnames=fieldnames,  delimiter=",")
    csv_file.writeheader()
    for line in new_csv:
        if None in line.keys():
            del line[None]
        csv_file.writerow(line)