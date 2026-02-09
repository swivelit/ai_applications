import csv

CSV_FILE = "theni_slang.csv"

def load_theni_slang():
    theni_map = {}
    with open(CSV_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            theni_map[row["normal_tamil"].strip()] = row["theni_slang"].strip()
    return theni_map


THENI_SLANG_MAP = load_theni_slang()


def tamil_to_theni(text):
    # long sentences first
    for normal in sorted(THENI_SLANG_MAP, key=len, reverse=True):
        text = text.replace(normal, THENI_SLANG_MAP[normal])
    return text
