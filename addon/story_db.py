import sqlite3
from threading import RLock
import json

import anki
import aqt
from .card_type import CardType
from . import config

from .util import addon_path, user_path, assure_user_dir, unique_characters, custom_list, list_to_primitive_str, get_proficiency_level_direction

story_db_path = addon_path("story.db")
usermod_db_path = user_path("usermod.db")

all_fields = ['source','primitives','keywords','primitive_keywords','story','comment','primitive_alternatives','conflicting_keywords','id']

user_modifiable_fields = ['primitives','keywords','primitive_keywords','story','comment']

main_keyword_source = 'h'  # selects which keyword set to compare possible conflicts

# When two characters reference each other as alternatives (for example 艹 -> 艸 and 艸 -> 艹 )
# then we want to link to the character which is the primary primitive
primary_primitives = ['艹','扌','⻖','⻏','川','罒','冫','月','辶','鼡','赤']

def json_loads_or_empty_list(l):
    if l is None or l == '':
        return []
    return json.loads(l)

def json_loads_or_none(l):
    if l is None:
        return None
    return json.loads(l)

def custom_or_empty_list(l):
    if l is None:
        return []
    return custom_list(l)

def conflicting_keyword_list(l):
    if l is None:
        return []
    # Conflicting keywords are given as 'source:keyword' pair. Filter
    # only those that match our main keyword source (default is Heisig keywords)
    conflicts = []
    kw_list = l.split(',')
    for kw in kw_list:
        kw = kw.split(':')
        if kw[0] == main_keyword_source:
            conflicts.append(kw[1])
    return conflicts


convert_data_from_db_func = {
    "primitives"                : custom_or_empty_list,
    "story"                  : json_loads_or_empty_list,
    "comment"                  : json_loads_or_empty_list,
    "keywords"                  : json_loads_or_empty_list,
    "primitive_keywords"        : json_loads_or_empty_list,
    "primitive_alternatives"    : custom_or_empty_list,
    "conflicting_keywords"        : conflicting_keyword_list,

    "mod_primitives"                : custom_list,
    "mod_story"                  : json_loads_or_none,
    "mod_comment"                  : json_loads_or_none,
    "mod_keywords"                  : json_loads_or_none,
    "mod_primitive_keywords"        : json_loads_or_none,
}
    
convert_data_to_db_func = {
    "primitives"                : list_to_primitive_str,
    "story"                  : json.dumps,
    "comment"                  : json.dumps,
    "keywords"                  : json.dumps,
    "primitive_keywords"        : json.dumps,

    "mod_primitives"                : list_to_primitive_str,
    "mod_story"                  : json.dumps,
    "mod_comment"                  : json.dumps,
    "mod_keywords"                  : json.dumps,
    "mod_primitive_keywords"        : json.dumps,
}

def data_from_db(field_name,data):
    #if data is not None and field_name in convert_data_from_db_func:
    if field_name in convert_data_from_db_func:
        f = convert_data_from_db_func[field_name]
        return f(data)
    return data

def data_to_db(field_name,data):
    if data is not None and field_name in convert_data_to_db_func:
        f = convert_data_to_db_func[field_name]
        return f(data)
    return data


class StoryDatabase:

    def __init__(self, parent):
        self.parent = parent
        self.initialize()

    # Open db
    def initialize(self):
        # check_same_thread set to false to allow gui thread updating while stuff is updated
        # only one thread ever accesses the db
        self.con = sqlite3.connect(story_db_path, check_same_thread=False)
        self.lock = RLock()

        self.crs = self.con.cursor()
        self.crs.execute("PRAGMA case_sensitive_like=OFF")

        self.crs.execute(f'ATTACH DATABASE "{usermod_db_path}" AS umod;')

        self.crs.execute(
            "CREATE TABLE IF NOT EXISTS stories ("
            "source TEXT NOT NULL,"
            "character TEXT NOT NULL,"
            'keywords TEXT DEFAULT NULL,'
            'primitive_keywords TEXT DEFAULT NULL,'
            'conflicting_keywords TEXT DEFAULT NULL,'
            'primitive_alternatives TEXT DEFAULT NULL,'
            'story TEXT DEFAULT NULL,'
            'comment TEXT DEFAULT NULL,'
            'primitives TEXT DEFAULT NULL,'
            'id TEXT DEFAULT NULL,'
            'PRIMARY KEY (source,character)'
            ")"
        )

        query = "CREATE TABLE IF NOT EXISTS umod.modified_values (" \
                "source TEXT NOT NULL," \
                "character TEXT NOT NULL,"

        field_list = [ 'mod_' + field_name + ' TEXT' for field_name in user_modifiable_fields]
        query += ', '.join(field_list) + ', PRIMARY KEY (source,character) )'
        self.crs.execute(query)
        self.con.commit()

        self.calculate_primitive_alternatives()
        self.calculate_primitive_of_cache()

    def crs_execute(self, __sql: str, __parameters=()):
        self.lock.acquire(True)
        self.crs.execute(__sql, __parameters)
        self.lock.release()

    def crs_execute_and_commit(self, __sql: str, __parameters=()):
        self.lock.acquire(True)
        self.crs.execute(__sql, __parameters)
        self.con.commit()
        self.lock.release()
    
    def crs_execute_and_fetch_one(self, __sql: str, __parameters=()):
        with self.lock:
            self.crs.execute(__sql, __parameters)
            r = self.crs.fetchone()
        return r

    def crs_execute_and_fetch_all(self, __sql: str, __parameters=()):
        self.lock.acquire(True)
        self.crs.execute(__sql, __parameters)
        r = self.crs.fetchall()
        self.lock.release()
        return r

    def crs_executemany_and_commit(self, __sql: str, __seq_of_parameters):
        self.lock.acquire(True)
        self.crs.executemany(__sql, __seq_of_parameters)
        self.con.commit()
        self.lock.release()

    def get_field(self, source, character, field_name):
        r = self.crs_execute_and_fetch_one(
            f"SELECT {field_name} FROM stories WHERE character=? and source=?",
            (character,source),
        )
        if r:
            return data_from_db(field_name,r[0])
        else:
            return data_from_db(field_name, "") # return anyway a correct type


    def _get_user_modified_field(self, source, character, field_name):
        assert field_name in user_modifiable_fields
        r = self.crs_execute_and_fetch_one(
            f"SELECT mod_{field_name} FROM umod.modified_values WHERE character=? AND source=?",
            (character,source),
        )
        if r:
            return True, data_from_db('mod_' + field_name,r[0])
        else:
            return False, None

    def get_user_modified_field(self, source, character, field_name):
        _, old_value = self._get_user_modified_field(source, character, field_name)
        return old_value

    def get_user_modified_field_or_original(self, source, character, field_name):
        value = self.get_user_modified_field(source, character, field_name)
        if value is None:
            value = self.get_field(source, character, field_name)
        return value

    def set_user_modified_field(self, source, character, field_name, data):
        self.lock.acquire(True)
        assert field_name in user_modifiable_fields
        original_value = self.get_field(source, character, field_name)
        if (data == original_value) or (data == "" and original_value is None) or (data == [''] and original_value == []):
            # Let's not keep duplicate values in the user database
            modified_data = None
        else:
            modified_data = data_to_db(field_name,data)
        row_exists, previous_user_defined_value = self._get_user_modified_field(source, character, field_name)
        previous_value = original_value if previous_user_defined_value is None else previous_user_defined_value
        if row_exists:
            self.crs.execute(
                f"UPDATE umod.modified_values SET mod_{field_name}=? WHERE character=? AND source=?",
                (modified_data,character,source),
            )
        else:
            if data is not None:
                self.crs.execute(
                    f"INSERT OR REPLACE INTO umod.modified_values (source,character,mod_{field_name}) VALUES (?,?,?)",
                    (source, character, modified_data),
                )
        if field_name == 'primitives':
            #self._recreate_primitive_of_references(character, field_name, previous_value, data)
            self.calculate_primitive_of_cache()
        self.parent.search_engine.update_cache(character)
        self.con.commit()
        self.lock.release()

        self.parent.refresh_notes_for_character(character)
        print("Updated %s:%s field '%s': %s -> %s" % (source, character, field_name, previous_value, data))


    def calculate_primitive_alternatives(self):

        self.primitive_alternative_reverse_lookup_table = dict()
        self.primitive_alternative_cache = dict()

        data = self.crs_execute_and_fetch_all(
            f"SELECT character, primitive_alternatives FROM stories WHERE primitive_alternatives IS NOT NULL"
        )
        for row in data:
            c = row[0]
            prim_alt_list = custom_list(row[1])
            self.primitive_alternative_cache[c] = prim_alt_list
            for p in prim_alt_list:
                self.primitive_alternative_reverse_lookup_table[p] = c

    def get_primary_primitive_from_alternative(self, alternative_primitive):
        if alternative_primitive not in primary_primitives:
            if alternative_primitive in self.primitive_alternative_reverse_lookup_table:
                return self.primitive_alternative_reverse_lookup_table[alternative_primitive]
        return alternative_primitive

    def calculate_primitive_of_cache(self):

        print("Calculating primitive_of cache..")
        data = self.crs_execute_and_fetch_all(
            f"SELECT source, character, primitives FROM stories WHERE primitives IS NOT NULL"
        )
        p_dict = dict()
        # Calculate primitive_of cache from Heisig / crowd-sourced primitives
        # but skip Wanikani because of so many errors in their data
        for row in data:
            if row[0] != 'wk':
                p_dict[ (row[0],row[1]) ] = row[2]

        mod_data = self.crs_execute_and_fetch_all(
            f"SELECT source, character, mod_primitives FROM umod.modified_values WHERE mod_primitives IS NOT NULL"
        )
        for row in mod_data:
            if row[0] != 'wk':
                p_dict[ (row[0],row[1]) ] = row[2]

        primitive_of = dict()

        for (src,c),p_list in p_dict.items():
            if p_list is not None:
                p_list = custom_list(p_list)
                for p in p_list:
                    p  = self.get_primary_primitive_from_alternative(p)
                    if p not in primitive_of:
                        primitive_of[p] = []
                    primitive_of[p].append(c)

        # Fetch frequency for each character
        self.parent.crs.execute("SELECT character,frequency_rank FROM characters")
        freq_data = self.parent.crs.fetchall()
        frequency = dict()
        for row in freq_data:
            kanji = row[0]
            frequency[kanji] = row[1]

        def sort_by_frequency(primitive_of_list):
            fr = dict()
            for k in primitive_of_list:
                if k in frequency:
                    fr[k] = frequency[k]
                else:
                    # kanji without frequency. Put it in the end
                    fr[k] = 100000
            sorted_k = sorted(fr.items(), key=lambda item: item[1])
            sorted_p = [p for (p,f) in sorted_k]
            return sorted_p

        self.primitive_of_cache = dict()
        for k, p_of_list in primitive_of.items():
            self.primitive_of_cache[k] = sort_by_frequency(p_of_list)

    def get_primitive_of(self, character):
        if character in self.primitive_of_cache:
            return self.primitive_of_cache[character]
        return []
    
    def add_alternative_primitives_to_list(self, p_list, add_only_existing_entries=False):
        new_p_list = []
        for p in p_list:
            new_p_list.append(p)
            if p in self.primitive_alternative_cache:
                for pa in self.primitive_alternative_cache[p]:
                    if pa not in new_p_list:
                        if add_only_existing_entries:
                            if self.parent.does_character_exist(pa, check_alternative_primitives=False):
                                new_p_list.append(pa)
                        else:
                            new_p_list.append(pa)
        return new_p_list
                
    def get_recursive_primitive_set(self, character, card_type):
        res = set([character])
        p_list = self.get_primitives(character, card_type)
        for p in p_list:
            if p not in res:
                rec_res = self.get_recursive_primitive_set(p, card_type)
                res.update(rec_res)
        return res

    def get_primitives(self, character, card_type, convert_to_primary_primitives=True):
        # Get primitives. If user has modified the primitive list, then use that by default. Otherwise fall back to the standard list
        primitives = self.get_user_modified_field_or_original('h',character,"primitives")

        # Add secondary or crowd-source primitives if available and user has enabled this setting
        if card_type.use_secondary_primitives:
            sec_primitives = self.get_user_modified_field_or_original('cs',character,"primitives")
            for p in sec_primitives:
                if not self.parent.is_primitive_rare(p, card_type):
                    if p not in primitives:
                        primitives.append(p)

        # Convert alternative primitive to the primary (e.g. 氵-> 水)
        if convert_to_primary_primitives:
            primitives = [self.get_primary_primitive_from_alternative(p) for p in primitives]
            
        return primitives

    # Fetch story elements (primitives, story, comment etc) for given kanji character.
    # Result is given as a dict of elements. Key is the story source (heisig, RRTK, ..)
    # If character=None, then story elements for ALL characters will be retrieved
    # and the dict key is a tuple: (source,character)
    def get_stories(self, character):

        fields = ",".join(all_fields)

        if character is not None:
            raw_data = self.crs_execute_and_fetch_all(
                f"SELECT {fields} FROM stories "
                "WHERE character = (?)",
                (character,),
            )
        else:
            raw_data = self.crs_execute_and_fetch_all(
                f"SELECT {fields},character FROM stories "
            )

        ret = {}
        for row in raw_data:
            
            cdata = {}
            # convert data from json to python data structures
            for data, field in zip(row, all_fields):
                if field in convert_data_from_db_func:
                    cdata[field] = convert_data_from_db_func[field](data)
                else:
                    cdata[field] = data

            if character is not None:
                source = cdata['source']
            else:
                source = (cdata['source'],row[-1])

            ret[source] = {}

            for field in all_fields[1:]:
                ret[source][field] = cdata[field]

            ret[source]['modified_fields'] = []

        self._overwrite_with_modified_story_elements(character, ret)

        return ret


    def _extract_main_keyword(self, keyword_source, stories):
        kw_list = stories[keyword_source]["keywords"]
        main_keyword = None
        if len(kw_list)>0:
            if keyword_source != 'h':
                main_keyword = kw_list[0]
            else:
                if len(kw_list)==2:
                    # select Heisig edition 6 keyword
                    main_keyword = kw_list[1]
                else:
                    # select Heisig edition 1-5 keyword
                    main_keyword = kw_list[0]
        if main_keyword is None:
            kw_list = stories[keyword_source]["primitive_keywords"]
            if len(kw_list)>0:
                main_keyword = kw_list[0]
        return main_keyword

    def extract_main_keyword(self, stories):
        main_keyword = None
        if main_keyword_source in stories:
            main_keyword = self._extract_main_keyword(main_keyword_source, stories)

        if main_keyword is None:
            for source in stories.keys():
                main_keyword = self._extract_main_keyword(source, stories)
                if main_keyword is not None:
                    return main_keyword

        return main_keyword

    # Because the FULL OUTER JOIN in sql3 is not supported, we have to do this 
    # separate ugly query to fetch modified elements 
    def _overwrite_with_modified_story_elements(self, character, result):

        fields = ['source'] + ['mod_' + field for field in user_modifiable_fields]
        fields_str = ",".join(fields)

        if character is not None:
            raw_data = self.crs_execute_and_fetch_all(
                f"SELECT {fields_str} FROM umod.modified_values "
                "WHERE character = (?)",
                (character,),
            )
        else:
            raw_data = self.crs_execute_and_fetch_all(
                f"SELECT {fields_str},character FROM umod.modified_values "
            )

        for row in raw_data:
            
            cdata = {}
            # convert data from json to python data structures
            for data, field in zip(row, fields):
                if field in convert_data_from_db_func:
                    cdata[field] = convert_data_from_db_func[field](data)
                else:
                    cdata[field] = data

            if character is not None:
                source = cdata['source']
            else:
                source = (cdata['source'],row[-1])

            if source not in result:
                # Initialize an empty entry for a source that didn't exist in original story.db
                result[source] = {}
                result[source]['modified_fields'] = []
                for field in all_fields:
                    if field in convert_data_from_db_func:
                        # hacky way to initialize proper structure 
                        result[source][field] = convert_data_from_db_func[field](None)
                    else:
                        result[source][field] = None

            # overwrite original with modified fields
            for field in user_modifiable_fields:
                data = cdata['mod_' + field]
                if data is not None:
                    result[source][field] = data
                    result[source]['modified_fields'].append(field)
