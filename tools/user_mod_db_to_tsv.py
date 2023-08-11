import sqlite3
import json
import sys
import os
import re
#
# A tool to extract user modified fields and output them to a .tsv patch file
#

user_modifiable_fields = ['primitives','sec_primitives','primitive_keywords','heisig_story','heisig_comment']

# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    if l is None:
        return None
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g

def json_loads_or_none(l):
    if l is None:
        return None
    return json.loads(l)

def list_to_primitive_str(l):
    return ''.join(l)

def to_json_list_str(csv):
    if csv!= '':
        item_list = csv.split(',')
        clean_list = [item.strip() for item in item_list]
        return json.dumps(clean_list)
    return '[]'

def j2c(d):
    return ", ".join(json.loads(d))


# (field_name, load_function, column)
_ = lambda x: x
requested_fields = [
    ("character", _, "characters.character"),
    ("stroke_count", _, None),
    ("onyomi", json.loads, None),
    ("kunyomi", json.loads, None),
    ("nanori", json.loads, None),
    ("meanings", json.loads, None),
    ("frequency_rank", _, None),
    ("grade", _, None),
    ("jlpt", _, None),
    ("kanken", _, None),
    ("primitives", custom_list, None),
    ("sec_primitives", custom_list, None),
    ("primitive_of", custom_list, None),
    ("primitive_keywords", json.loads, None),
    ("primitive_alternatives", custom_list, None),
    ("heisig_id5", _, None),
    ("heisig_id6", _, None),
    ("heisig_keyword5", _, None),
    ("heisig_keyword6", _, None),
    ("heisig_story", _, None),
    ("heisig_comment", _, None),
    ("radicals", list, None),
    ("words_default", json.loads, None),
    ("koohi_stories", json.loads, None),
    ("wk", _, None),
    ("usr_keyword", _, "usr.keywords.usr_keyword"),
    ("usr_primitive_keyword", _, "usr.keywords.usr_primitive_keyword"),
    ("usr_story", _, "usr.stories.usr_story"),
    ("mod_heisig_story", _, "usr.modified_values.mod_heisig_story"),
    ("mod_heisig_comment", _, "usr.modified_values.mod_heisig_comment"),
    ("mod_primitives", custom_list, "usr.modified_values.mod_primitives"),
    ("mod_sec_primitives", custom_list, "usr.modified_values.mod_sec_primitives"),
    ("mod_primitive_keywords", json_loads_or_none, "usr.modified_values.mod_primitive_keywords"),
]

convert_data_from_db_to_str_func = {
    "onyomi"                    : j2c,
    "kunyomi"                   : j2c,
    "nanori"                    : j2c,
    "meanings"                  : j2c,
    "primitive_keywords"        : j2c,
    "words_default"             : j2c,
    "koohi_stories"             : j2c,
}

def data_from_db_to_str(field_name,data):
    if data is not None and field_name in convert_data_from_db_to_str_func:
        f = convert_data_from_db_to_str_func[field_name]
        return f(data)
    return data

kanji_db_path = sys.argv[1] if len(sys.argv) > 1 else "addon/kanji.db"
user_db_path = sys.argv[2] if len(sys.argv) > 2 else "addon/user_files/user.db"
tsv_path = sys.argv[3] if len(sys.argv) > 3 else "kanji-usermod-patch.tsv"

con = sqlite3.connect(kanji_db_path)
crs = con.cursor()

crs.execute(f'ATTACH DATABASE "{user_db_path}" AS usr;')

fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

joins = [
    f"LEFT OUTER JOIN usr.keywords ON characters.character == usr.keywords.character ",
    f"LEFT OUTER JOIN usr.stories ON characters.character == usr.stories.character ",
    f"LEFT OUTER JOIN usr.modified_values ON characters.character == usr.modified_values.character "
]
joins_txt = "".join(joins)

crs.execute(
    f"SELECT {fields} FROM characters {joins_txt}"
)
rows = crs.fetchall()


f = open(tsv_path, "w", encoding="utf-8")

def fw(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    f.write("\t".join(args))
    f.write("\n")
    print("\t".join(args))

# write header
fw( [
    "Kanji",
    "Field",
    "OldValue",
    "NewValue",
]
)

for raw_data in rows:

    ret = {}

    for data, (name, load_func, _) in zip(raw_data, requested_fields):
        ret[name] = data #load_func(data)

    character = ret['character']

    for field in user_modifiable_fields:
        orig_data = data_from_db_to_str(field,ret[field]) or ''
        user_mod_data = data_from_db_to_str(field,ret['mod_' + field])

        if user_mod_data is not None:
            user_mod_data = user_mod_data.replace('\n','')
            user_mod_data = user_mod_data.replace('\r','')

            if orig_data == user_mod_data:
                print("%s: user modified field %s has value %s which equals original. Should be cleaned!" % (character, field, orig_data))
            else:
                change = [character,field,orig_data,user_mod_data]
                fw(change)

f.close()
