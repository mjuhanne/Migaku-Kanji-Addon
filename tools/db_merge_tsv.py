#
# Merges changed kanjis/primitives listed in kanji-ext.tsv with kanji.db
#
import sqlite3
import json
import sys
import os
import re
import logging

simulate = False

kanji_db_fields = [
    "character",
    "meanings",
    "radicals",
    "primitive_of",
]

story_db_fields = [
    "keywords",
    "primitives",
    "primitive_keywords",
    "primitive_alternatives",
    "story",
    "comment",
    "conflicting_keywords",
    "id",
]

user_modifiable_fields = {    
    "primitives" : "umod.modified_values.mod_primitives",
    "keywords": "umod.modified_values.mod_keywords",
    "primitive_keywords": "umod.modified_values.mod_primitive_keywords",
    "story" : "umod.modified_values.mod_story",
    "comment" : "umod.modified_values.mod_comment",
}

def to_json_list_str(csv):
    if csv!= '':
        item_list = csv.split(',')
        clean_list = [item.strip() for item in item_list]
        return json.dumps(clean_list)
    return '[]'

def j2c_or_none(d):
    if d is None or d == '':
        return None
    return ", ".join(json.loads(d))

def story_json_dumps(d):
    if d == '':
        return '[]'
    if d[0] != '[' or d[-1] != ']': 
        # the value wasn't stored as JSON representation of list of strings 
        # but a single string so convert to array of a single string and then do
        # JSON dump
        d = json.dumps( [d] )
    return d

def story_j2c(d):
    if d is None or d == '':
        return []
    if d[0] != '[' or d[-1] != ']': 
        # the value wasn't stored as JSON representation of list of strings 
        # but a single string so convert to array of a single string
        return [d]
    return json.loads(d)

_ = lambda x: x

field_conversion_to_db_schema = {
    "story" : story_json_dumps,
    "comment" : story_json_dumps,
    "meanings" : to_json_list_str,
    "keywords" : to_json_list_str,
    "primitive_keywords" : to_json_list_str,
    "mod_keywords" : to_json_list_str,
    "mod_primitive_keywords" : to_json_list_str,
}

field_conversion_from_db_schema = {
    "story" : story_j2c,
    "comment" : story_j2c,
    "meanings" : j2c_or_none,
    "keywords" : j2c_or_none,
    "primitive_keywords" : j2c_or_none,
    "mod_keywords" : j2c_or_none,
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
#ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "../Migaku-Kanji-Addon/stories-db.tsv"
#ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "../Migaku-Kanji-Addon/kanji-db-koohi.tsv"
#ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "../Migaku-Kanji-Addon/wk.tsv"
#ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "../Migaku-Kanji-Addon/rrtk.tsv"
ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "../Migaku-Kanji-Addon/kanji-usermod-patch.tsv"
#ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "../Migaku-Kanji-Addon/kanji-db-ids.tsv"

db_path = sys.argv[2] if len(sys.argv) > 2 else "../Migaku-Kanji-Addon/addon/kanji.db"
story_db_path = sys.argv[2] if len(sys.argv) > 2 else "../Migaku-Kanji-Addon/addon/story.db"
usermod_db_path = sys.argv[3] if len(sys.argv) > 3 else "../Migaku-Kanji-Addon/addon/user_files/usermod.db"
log_path = sys.argv[4] if len(sys.argv) > 4 else "../Migaku-Kanji-Addon/db_merge_new_log.md"
db_path = os.path.abspath(db_path)

### set up logging
targets = logging.StreamHandler(sys.stdout), logging.FileHandler(log_path,'w+')
logging.basicConfig(format='%(message)s', level=logging.INFO, handlers=targets)

con = sqlite3.connect(db_path)
crs = con.cursor()

story_db_con = sqlite3.connect(story_db_path)
story_crs = story_db_con.cursor()
story_crs.execute(f'ATTACH DATABASE "{usermod_db_path}" AS umod;')


processed_kanji_list = []
total_changes = 0
line_number = 0

previous_kanji = None

def clean_user_modified_field(source,kanji,field_name,new_data):
    mod_field_name = 'mod_' + field_name

    story_crs.execute(
        f'SELECT {user_modifiable_fields[field_name]} FROM umod.modified_values WHERE character == (?) AND source == (?)',
        (kanji, source),
    )
    res = story_crs.fetchall()
    if len(res) > 0:
        user_modified_data = res[0][0]
        if user_modified_data == new_data:
            logging.info('#### %s: Cleaning also user modified field: %s ' % (kanji,mod_field_name))
            # let's not leave identical data laying around in the user mod column
            if not simulate:
                update_sql = (
                    f'UPDATE umod.modified_values SET {mod_field_name}=? WHERE character=? AND source=?'
                )
                updated_data_tuple = (None, kanji, source)
                story_crs.execute(update_sql, updated_data_tuple)
                story_db_con.commit()


for l in open(ext_tsv_path, "r", encoding="utf-8"):
    
    line_number += 1

    d = l.replace("\n", "").split("\t")
    if len(d[0]) == 0:
        logging.info("")
        continue
    if d[0] == 'Source':
        # process the header
        if d[1:] != ['Character','Field','OldValue','NewValue']:
            raise Exception("Error in file format!")
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

    source = d[0]
    kanji = d[1]

    if len(d) == 3 and d[2] == 'DELETE':
        logging.info("# DELETE %s from %s" %(kanji,source))
        if not simulate:
            if source == 'k':
                delete_sql = (
                    f'DELETE FROM characters WHERE character=?'
                )
                crs.execute(delete_sql, (d[0],) )
                con.commit()
            else:
                delete_sql = (
                    f'DELETE FROM stories WHERE character=? AND source=?'
                )
                story_crs.execute(delete_sql, (kanji,source) )
                story_db_con.commit()
        continue


    field_name = d[2]
    previous_data = d[3]
    non_converted_new_data = d[4]
    character_field_tuple = (source,kanji,field_name)
    
    # convert data to json format for modifying the database
    if field_name in field_conversion_to_db_schema:
        converted_new_data = field_conversion_to_db_schema[field_name](non_converted_new_data)
    else:
        converted_new_data = non_converted_new_data

    if character_field_tuple in processed_kanji_list:
            raise Exception("Kanji %s already processed! Remove duplicate from line %d" % (character_field_tuple,line_number))

    # Check if a card already exists for this character
    if source == 'k':
        # Kanji DB
        if field_name not in kanji_db_fields:
            raise Exception("Unknown field name %s in line %d" % (character_field_tuple,line_number))

        selected_sql_field_names = [field_name]
        crs.execute(
            f'SELECT {",".join(selected_sql_field_names)} FROM characters WHERE character == (?)',
            (kanji,),
        )
        res = crs.fetchall()
    else:
        # Story DB
        if field_name not in story_db_fields:
            raise Exception("Unknown field name %s in line %d" % (character_field_tuple,line_number))

        story_crs.execute(
            f'SELECT {field_name} FROM stories LEFT OUTER JOIN umod.modified_values ON stories.character == umod.modified_values.character AND stories.source == umod.modified_values.source WHERE stories.character == (?) AND stories.source == (?)',
            (kanji,source),
        )
        res = story_crs.fetchall()

    if len(res) > 1:
        raise Exception("%s contains more than 1 entry! Should not happen!" % (character_field_tuple))

    if len(res) == 1:

        existing_data = res[0][0]
        if field_name in field_conversion_from_db_schema:
            existing_data_str = field_conversion_from_db_schema[field_name](existing_data)
        else:
            existing_data_str = existing_data

        new_data = converted_new_data

        if (existing_data != new_data) and not (existing_data is None and new_data==''):

            if not simulate:
                if source == 'k':
                    update_sql = (
                        f'UPDATE characters SET {field_name}=? WHERE character=?'
                    )
                    updated_data_tuple = (new_data, kanji)
                    crs.execute(update_sql, updated_data_tuple)
                    con.commit()
                else:
                    update_sql = (
                        f'UPDATE stories SET {field_name}=? WHERE character=? AND source=?'
                    )
                    updated_data_tuple = (new_data, kanji, source)
                    story_crs.execute(update_sql, updated_data_tuple)
                    story_db_con.commit()

            if kanji != previous_kanji:
                logging.info('#### ' + kanji)

                logging.info("| Source | Field | Old value | New value |" )
                logging.info("|---|---|---|---|" )

            logging.info("| %s | %s | %s | %s |" % (source.ljust(4), field_name.ljust(20), existing_data_str, new_data))
            total_changes += 1

        if field_name in user_modifiable_fields:
            clean_user_modified_field(source,kanji,field_name,new_data)

    else:

        logging.info("#### [%s] %s (NEW ITEM)" % (source,kanji))

        logging.info("| Source | Field | Value |" )
        logging.info("|---|---|---|" )
        logging.info("| %s | %s | %s |" % (source, field_name, converted_new_data))
        total_changes += 1

        if not simulate:
            if source == 'k':
                insert_sql = (
                    f'INSERT OR IGNORE into characters (character,{field_name}) values (?,?)'
                )
                insert_data_tuple = (kanji, converted_new_data)
                crs.execute(insert_sql, insert_data_tuple)
                con.commit()
            else:
                insert_sql = (
                    f'INSERT OR IGNORE into stories (source,character,{field_name}) values (?,?,?)'
                )
                insert_data_tuple = (source, kanji, converted_new_data)
                story_crs.execute(insert_sql, insert_data_tuple)
                story_db_con.commit()

        if field_name in user_modifiable_fields:
            clean_user_modified_field(source,kanji,field_name,converted_new_data)


    previous_kanji = kanji

logging.info("Processed %d items with total %d changes" % (len(processed_kanji_list), total_changes))

