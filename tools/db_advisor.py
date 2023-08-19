import sqlite3
import json
import sys
import os
import re

# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g

ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "addon/kanji-ext.tsv"
db_path = sys.argv[2] if len(sys.argv) > 2 else "addon/kanji.db"

db_path = os.path.abspath(db_path)

con = sqlite3.connect(db_path)
#con.row_factory = sqlite3.Row
crs = con.cursor()

fields = [
    "character",
    "meanings",
    "primitive_alternatives",
    "primitives",
    "heisig_keyword5",
    "heisig_keyword6",
    "primitive_keywords",
    "heisig_story",
    "heisig_comment",
    "radicals",
]

def to_json_list_str(d):
    if d!= '':
        return json.dumps(d.replace(' ','').split(','))
    return '[]'

def to_list_str(d):
    if d!= '':
        return str( d.replace(' ','').split(',') )
    return '[]'

def to_list(d):
    if d!= '':
        return d.replace(' ','').split(',') 
    return '[]'

# (field_name, load_function, column)
_ = lambda x: x
field_conversion = [
    (0,"character", _, None),
    (1,"meanings", to_list, None),
    (2,"primitive_alternatives", _, None),
    (3,"primitives", _, None),
    (4,"heisig_keyword5", _, None),
    (5,"heisig_keyword6", _, None),
    (6,"primitive_keywords", to_json_list_str, None),
    (7,"heisig_story", _, None),
    (8,"heisig_comment", _, None),
    (9,"radicals", to_list_str, None),
]


def fw(*args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    return "\t".join(args)



def j2c(d):
    if d is not None:
        return ", ".join(json.loads(d))
    else:
        return ""




crs.execute("SELECT * FROM characters")
db_data = crs.fetchall()

column_names = [description[0] for description in crs.description]
print("kanji.db column names:", column_names)

story = column_names.index('primitive_of')

primitives = []

for line in open(ext_tsv_path, "r", encoding="utf-8"):
    l = line.replace("\n", "").split("\t")
    if l[0] == 'Kanji':  # omit the header
        continue

    if len(l) != 10:
        print("Error! Wrong length in data: ",d)
        continue

    kanji = l[0].strip()

    #print("Processing", kanji)

    converted_l = l

    for data, (idx, name, load_func, _) in zip(l, field_conversion):
        converted_l[idx] = load_func(data)
    
    meaning = converted_l[1][0]

    name = converted_l[0]
    clean_name = name[1:-1] if name[0] == '[' else name
    clean_name = clean_name.replace('_',' ')

    print("########### ",l[0],meaning)
    print(line)

    for d in db_data:

        if d[17] is not None and (meaning in d[17] or clean_name in d[17]):
            res = fw(
                    d[0],
                    j2c(d[5]), #d[5],
                    d[12],
                    d[10],
                    d[15] or "",
                    d[16] or "",
                    j2c(d[11]),
                    d[17] or "",
                    d[18] or "",
                    d[19],
                )
            print(res)
            #print(data)
    print("")

con.close()