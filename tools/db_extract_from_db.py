import sqlite3
import json
import sys
from collections import OrderedDict

def j2c(d):
    return ", ".join(json.loads(d))

# (field_name, load_function, column)
_ = lambda x: x
requested_fields = [
    ("character", _, "characters.character"),
    ("meanings", j2c, None),
    ("primitive_alternatives", _, None),
    ("primitives", _, None),
    ("primitive_keywords", j2c, None),
    ("heisig_keyword5", _, None),
    ("heisig_keyword6", _, None),
    ("heisig_story", _, None),
    ("heisig_comment", _, None),
    ("radicals", _, None),
]


def fw(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    f.write("\t".join(args))
    f.write("\n")


processed_line_dict = OrderedDict()

comment_number = 0

total_changes = 0
line_number = 0

line_format = None

#original_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "migaku-kanji-db-2022-01-11-my.tsv"
original_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "migaku-kanji-db.tsv"
target_tsv_path = sys.argv[2] if len(sys.argv) > 2 else "migaku-db-improved.tsv"
kanji_db_path = sys.argv[3] if len(sys.argv) > 3 else "addon/kanji.db"

con = sqlite3.connect(kanji_db_path)
crs = con.cursor()

fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

crs.execute(
    f"SELECT {fields} FROM characters"
)
rows = crs.fetchall()

db_data = dict()

for row in rows:

    new_row = []
    for data,(field_name,func,_notused) in zip(row,requested_fields):
        if data is None:
            data = ''
        new_row.append(func(data))

    db_data[row[0]] = new_row

column_names = [description[0] for description in crs.description]
print("kanji.db column names:", column_names)


f = open(target_tsv_path, "w", encoding="utf-8")
fi = open(original_tsv_path, "r", newline='\n', encoding="utf-8")

data = fi.read()
countr = data.count('\r')
countn = data.count('\n')
data = data.replace('\r','')
countr = data.count('\r')
countn = data.count('\n')

lines = data.split('\n')
fw(column_names)
for l in lines:
    
    line_number += 1

    d = l.replace("\n", "").split("\t")

    c = d[0]

    if c in db_data:
        fw(db_data[c])
        db_data.pop(c)
    else:
        if line_number != 1:
            print("Warning! %d: %s not in db!" % (line_number,c))
            print("\t",d)
            d[0] = 'REMOVED'
            fw(d)


for c,row in db_data.items():
    print(c)
    fw(row)

f.close()

