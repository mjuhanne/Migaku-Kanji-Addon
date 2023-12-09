import sqlite3
import json
import sys
import os
import re
#
# A tool to extract user modified fields and output them to a .tsv patch file
#

user_modifiable_fields = ['primitives','keywords','primitive_keywords','story','comment']

def j2c_or_none(d):
    if d is None or d == '':
        return None
    return ", ".join(json.loads(d))

def story_j2c(d):
    if d is None or d == '' or d == '[]':
        return ''
    d = json.loads(d)
    if len(d)==1:
        s = d[0]
        if '\n' not in s and '\r' not in s:
            return s
    return json.dumps(d)


convert_data_from_db_to_str_func = {
    "keywords"                : j2c_or_none,
    "primitive_keywords"      : j2c_or_none,
    "story"                   : story_j2c,
    "comment"                 : story_j2c,
}

def data_from_db_to_str(field_name,data):
    if data is not None and field_name in convert_data_from_db_to_str_func:
        f = convert_data_from_db_to_str_func[field_name]
        return f(data)
    return data

story_db_path = sys.argv[1] if len(sys.argv) > 1 else "addon/story.db"
user_mod_db_path = sys.argv[2] if len(sys.argv) > 2 else "addon/user_files/usermod.db"
tsv_path = sys.argv[3] if len(sys.argv) > 3 else "kanji-usermod-patch.tsv"

story_con = sqlite3.connect(story_db_path)
story_crs = story_con.cursor()

user_con = sqlite3.connect(user_mod_db_path)
user_crs = user_con.cursor()


fields = ['source','character'] + ['mod_' + field for field in user_modifiable_fields]
fields_str = ','.join(fields)

user_crs.execute(
    f"SELECT {fields_str} FROM modified_values"
)
mod_rows = user_crs.fetchall()


f = open(tsv_path, "w", encoding="utf-8")

def fw(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    f.write("\t".join(args))
    f.write("\n")
    print("\t".join(args))

# write header
fw( [
    "Source",
    "Character",
    "Field",
    "OldValue",
    "NewValue",
]
)

orig_fields = [field for field in user_modifiable_fields]
orig_fields_str = ','.join(orig_fields)

for raw_data in mod_rows:

    new_data = {}

    for data, field in zip(raw_data, fields):
        new_data[field] = data #load_func(data)

    character = new_data['character']
    source = new_data['source']

    story_crs.execute(
        f"SELECT {orig_fields_str} FROM stories WHERE character == ? AND source == ?",
        (character,source)
    )
    orig_rows = story_crs.fetchall()
    orig_data = {}
    if len(orig_rows) == 1:
        for data, field in zip(orig_rows[0], orig_fields):
            orig_data[field] = data_from_db_to_str(field,data) #load_func(data)

    for field in user_modifiable_fields:
        if field in orig_data:
            old_data = orig_data[field] or ''
        else:
            old_data = ''
            
        user_mod_data = data_from_db_to_str(field,new_data['mod_' + field])

        if user_mod_data is not None:
            user_mod_data = user_mod_data.replace('\n','')
            user_mod_data = user_mod_data.replace('\r','')

            if old_data == user_mod_data:
                print("%s: user modified field %s has value %s which equals original. Should be cleaned!" % (character, field, orig_data))
            else:
                change = [source,character,field,old_data,user_mod_data]
                fw(change)

f.close()
