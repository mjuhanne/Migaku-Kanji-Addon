#
# Merges changed kanjis/primitives listed in given .tsv file with kanji.db. 
# Recalculates also primitives-of list for each kanji
# 
# .tsv files can be in the same format as the Migaku Kanji Database 
# excel file (https://docs.google.com/spreadsheets/d/1aw0ihw0RpmejWLTUynrFYjmOfLdzcPVrDX7UM50lwBY)
# or patch file which has one updated field per line (as the format used by user_mod_db_to_tsv.py)
#
# If updated fields contain the same data as in the user modified field (e.g. modified Heisig 
# comment or primitives list), clean out the respective user modified field.
#
import sqlite3
import json
import sys
import os
import re
import logging

LINE_FORMAT_SHORT = 0
LINE_FORMAT_LONG = 1

standard_fields = [
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

user_modifiable_fields = {
    "primitives" : "usr.modified_values.mod_primitives",
    "primitive_keywords": "usr.modified_values.mod_primitive_keywords",
    "heisig_story" : "usr.modified_values.mod_heisig_story",
    "heisig_comment" : "usr.modified_values.mod_heisig_comment",
}

def to_json_list_str(csv):
    if csv!= '':
        item_list = csv.split(',')
        clean_list = [item.strip() for item in item_list]
        return json.dumps(clean_list)
    return '[]'

def j2c_or_none(d):
    if d is None:
        return None
    return ", ".join(json.loads(d))

_ = lambda x: x

field_conversion_to_db_schema = {
    "meanings" : to_json_list_str,
    "primitive_keywords" : to_json_list_str,
    "mod_primitive_keywords" : to_json_list_str,
}

field_conversion_from_db_schema = {
    "meanings" : j2c_or_none,
    "primitive_keywords" : j2c_or_none,
    "mod_primitive_keywords" : j2c_or_none,
}

# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    if l is None:
        return None
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g

# create multi-line string for better readibility in markdown tables
def multiLine(src_list,n):    
    chunks = [src_list[i:i+n] for i in range(0, len(src_list), n)]
    lines = [ ''.join(chunk) for chunk in chunks ]            
    return '<br>'.join(lines)

#ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "addon/kanji-ext4.tsv"
ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "kanji-usermod-patch-5.tsv"
db_path = sys.argv[2] if len(sys.argv) > 2 else "addon/kanji.db"
user_db_path = sys.argv[3] if len(sys.argv) > 3 else "addon/user_files/user.db"
log_path = sys.argv[4] if len(sys.argv) > 4 else "db_merge_log.md"
db_path = os.path.abspath(db_path)

### set up logging
targets = logging.StreamHandler(sys.stdout), logging.FileHandler(log_path,'w+')
logging.basicConfig(format='%(message)s', level=logging.INFO, handlers=targets)

con = sqlite3.connect(db_path)
crs = con.cursor()
crs.execute(f'ATTACH DATABASE "{user_db_path}" AS usr;')

processed_kanji_list = []
total_changes = 0
line_number = 0

line_format = None

selected_sql_field_names = []
selected_field_names = []
selected_standard_field_names = []

def create_field_selectors_and_convertors(fields):
    global selected_sql_field_names, selected_field_names, selected_standard_field_names, \
        field_conversion_to_db, field_conversion_from_db

    selected_standard_field_names = fields.copy()
    selected_field_names = fields.copy()
    selected_sql_field_names = fields.copy()

    for field in fields:
        if field in user_modifiable_fields:
            selected_sql_field_names.append(user_modifiable_fields[field])
            field_name = 'mod_' + field
            selected_field_names.append(field_name)

    field_conversion_from_db = [ (field,field_conversion_from_db_schema[field])
        if field in field_conversion_from_db_schema
        else (field, _)
        for field in selected_field_names 
    ]
    field_conversion_to_db = [ (field,field_conversion_to_db_schema[field])
        if field in field_conversion_to_db_schema
        else (field, _)
        for field in selected_standard_field_names 
    ]


previous_kanji = None

for l in open(ext_tsv_path, "r", encoding="utf-8"):
    
    line_number += 1

    d = l.replace("\n", "").split("\t")
    if len(d[0]) == 0:
        logging.info("")
        continue
    if d[0] == 'Kanji' or d[0] == 'character':
        # process the header
        if d == ['Kanji','Field','OldValue','NewValue']:
            # File consists of 1 change per line
            line_format = LINE_FORMAT_SHORT
            if len(d) != 4:
                raise Exception("Error in file format!")
        else:
            line_format = LINE_FORMAT_LONG
            if len(d) != 10:
                raise Exception("Error in file format!")
            fields = d.copy()
            fields = fields[1:] # omit character
            create_field_selectors_and_convertors(fields)
        continue
    if d[0][0]=='#':  # only log the comments
        # modify the comments so they look better in markdown
        hash_count = d[0].count('#')
        cleaned_comment = d[0].replace('#', '')
        if hash_count > 5:
            logging.info('----')
            comment = '## ' + cleaned_comment
        elif hash_count > 1:
            comment = '###' + cleaned_comment
        else:
            comment = '####' + cleaned_comment
        logging.info(comment)
        continue
    if d[1] == 'DELETE':
        logging.info("# DELETE %s",d[0])
        delete_sql = (
            f'DELETE FROM characters WHERE character=?'
        )
        crs.execute(delete_sql, (d[0],) )
        con.commit()
        continue

    if line_format == LINE_FORMAT_LONG:
        if len(d) != 10:
            raise Exception("Error! Line %d - wrong length in data: %s" % (line_number, str(d)))
    elif line_format == LINE_FORMAT_SHORT:
        if len(d) != 4:
            raise Exception("Error! Line %d - wrong length in data: %s" % (line_number, str(d)))
        fields = [d[1]]
        create_field_selectors_and_convertors(fields)
        previous_value = d[2]
        # this is the new [character,new value] pair
        d = [d[0],d[3]]
    else:
        raise Exception("Error! No header defined!")

    kanji = d[0].strip()
    
    new_data_list = d[1:] # omit character
    new_data_per_field = dict()
    for field,data in zip(selected_standard_field_names,new_data_list):
        new_data_per_field[field] = data

    # convert data to json format for modifying the database
    converted_new_data_per_field = dict()
    for data, (field_name, load_func) in zip(new_data_list, field_conversion_to_db):
        converted_new_data_per_field[field_name] = load_func(data)

    if kanji in processed_kanji_list:
        if line_format == LINE_FORMAT_LONG:
            raise Exception("Kanji %s already processed! Remove duplicate from line %d" % (kanji,line_number))
    else:
        processed_kanji_list.append(kanji)

    # create printable header
    pretty_header = kanji
    if line_format == LINE_FORMAT_LONG:
        pkw = new_data_per_field["primitive_keywords"]
        kw = new_data_per_field["heisig_keyword5"]
        if kw != '':
            pretty_header += ' ' + kw
            if pkw != '':
                pretty_header += ' / ' + pkw
        elif pkw != '':
            pretty_header += ' ' + pkw
        pretty_header += ' (' + new_data_per_field["meanings"] + ')'

    # Check if a card already exists for this character
    crs.execute(
        f'SELECT {",".join(selected_sql_field_names)} FROM characters LEFT OUTER JOIN usr.modified_values ON characters.character == usr.modified_values.character WHERE characters.character == (?)',
        (kanji,),
    )

    res = crs.fetchall()
    if len(res) > 0:

        existing_data_list = list(res[0])
        existing_data_per_field = dict()
        for field,data in zip(selected_field_names,existing_data_list):
            existing_data_per_field[field] = data

        # old data: create value strings for better readibility
        existing_data_str_per_field = dict()
        for data, (field_name, load_func) in zip(existing_data_list, field_conversion_from_db):
            existing_data_str_per_field[field_name] = load_func(data)
        
        updated_fields = []
        updated_data = []
        to_be_cleaned_user_mod_fields = dict()

        for field in selected_standard_field_names:

            existing_data = existing_data_per_field[field]
            new_data = converted_new_data_per_field[field]
            if (existing_data != new_data) and not (existing_data is None and new_data==''):

                if len(updated_fields)==0 and kanji != previous_kanji:
                    logging.info('#### ' + pretty_header)

                    logging.info("| Field | Old value | New value |" )
                    logging.info("|---|---|---|" )

                logging.info("| %s | %s | %s |" % (field.ljust(20), existing_data_str_per_field[field], new_data_per_field[field]))
                total_changes += 1

                updated_fields.append(field)
                updated_data.append(new_data)

            if field in user_modifiable_fields:
                mod_field_name = 'mod_' + field
                user_modified_data = existing_data_per_field[mod_field_name]
                if user_modified_data == new_data:
                    # let's not leave identical data laying around in the user mod column
                    to_be_cleaned_user_mod_fields[mod_field_name] = None
                    logging.info('#### %s: Cleaning also user modified field: %s ' % (kanji,mod_field_name))


        if len(updated_fields)>0:
            update_sql = (
                f'UPDATE characters SET {"=? , ".join(updated_fields)}=? WHERE character=?'
            )
            updated_data_tuple = (*updated_data, kanji)
            crs.execute(update_sql, updated_data_tuple)
            con.commit()

        if len(to_be_cleaned_user_mod_fields)>0:
            update_sql = (
                f'UPDATE usr.modified_values SET {"=? , ".join(to_be_cleaned_user_mod_fields.keys())}=? WHERE character=?'
            )
            updated_data_tuple = (*to_be_cleaned_user_mod_fields.values(), kanji)
            crs.execute(update_sql, updated_data_tuple)
        con.commit()

    else:

        logging.info("#### %s (NEW ITEM)" % pretty_header)

        logging.info("| Field | Value |" )
        logging.info("|---|---|" )

        # convert data to json format for modifying to database
        for field in selected_standard_field_names:
            logging.info("| %s | %s |" % (field, converted_new_data_per_field[field]))
            total_changes += 1


        insert_sql = (
            f'INSERT OR IGNORE into characters ({",".join(converted_new_data_per_field.keys())}) values ({",".join("?"*len(converted_new_data_per_field))})'
        )
        insert_data_tuple = (*converted_new_data_per_field.values(), kanji)

        crs.execute(insert_sql, insert_data_tuple)
        con.commit()

    previous_kanji = kanji

logging.info("Processed %d items with total %d changes" % (len(processed_kanji_list), total_changes))

##################################################################
print("Reconstructing primitive_of lists..")

crs.execute("SELECT * FROM characters LEFT OUTER JOIN usr.modified_values ON characters.character == usr.modified_values.character")
data = crs.fetchall()

column_names = [description[0] for description in crs.description]
print("kanji.db column names:", column_names)

poi_i = column_names.index('primitive_of')
pi_i = column_names.index('primitives')
ci_i = column_names.index('character')
ri_i = column_names.index('radicals')
hk_i = column_names.index('heisig_keyword6') 
pk_i = column_names.index('primitive_keywords') 
m_i = column_names.index('meanings') 
mpi_i = column_names.index('mod_primitives')

primitive_of_dict = dict()

# Create a lookup table for primitives that are being used by kanjis or other primitives
for row in data:
    character = row[ci_i]
    primitives = custom_list(row[pi_i])
    mod_primitives = custom_list(row[mpi_i])

    if mod_primitives is not None:
        for p in mod_primitives:
            if p not in primitive_of_dict:
                primitive_of_dict[p] = ""
            if p != character:
                primitive_of_dict[p] += character
    else:
        for p in primitives:
            if p not in primitive_of_dict:
                primitive_of_dict[p] = ""
            if p != character:
                primitive_of_dict[p] += character


# Re-calculate primitive_of references

logging.info("# Changes in primitives-of list")
logging.info("| Kanji | Meaning/Keyword | Added | Removed |")
logging.info("|---|---|---|---|")
for row in data:
    character = row[ci_i]
    orig_primitive_of = custom_list(row[poi_i])
    orig_primitive_of_set = set(orig_primitive_of)
    if character in primitive_of_dict:
        primitive_of_set = set(custom_list(primitive_of_dict[character]))
    else:
        primitive_of_set = set()

    # extract the best representation for the kanji/primitive name
    if row[hk_i] is not None and row[hk_i] != '':
        name = row[hk_i]
    elif row[pk_i] is not None and row[pk_i] != '[]':
        name = j2c_or_none(row[pk_i])
    elif row[m_i] is not None and row[m_i] != '[]':
        name = j2c_or_none(row[m_i])
    else:
        name = ""

    if primitive_of_set != orig_primitive_of_set:

        added = multiLine(list(primitive_of_set-orig_primitive_of_set),10)
        removed = multiLine(list(orig_primitive_of_set - primitive_of_set),10)
        logging.info('|' + character + " | " + name + " | " + added + " | " + removed + ' |')
        new_primitive_of_set = primitive_of_set
        new_data = [''.join(new_primitive_of_set), character]

        update_prim_of_sql = (
            f'UPDATE characters SET primitive_of=? WHERE character=?'
        )

        crs.execute(update_prim_of_sql, new_data)
        con.commit()

con.close()
