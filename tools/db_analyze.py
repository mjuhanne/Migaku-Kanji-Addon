import sqlite3
import json
import sys
import os
import re
import argparse

DEFAULT_KANJI_DB_PATH = "addon/kanji.db"
DEFAULT_USER_DB_PATH = "addon/user_files/user.db"


# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g

def fw(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    return "\t".join(args)

def j2c(d):
    if d is not None:
        item = json.loads(d)
        return ", ".join(item)
    else:
        return ""

def jl2c(d):
    if d is not None:
        output_str = ''
        item_list = json.loads(d)
        for item in item_list:
            output_str = '"' +  ", ".join(item) + '"'
        return output_str
    else:
        return ""

# (field_name, load_function, column)
_ = lambda x: x
requested_fields = [
    ("character", _, "characters.character"),
    ("stroke_count", _, None),
    ("onyomi", j2c, None),
    ("kunyomi", j2c, None),
    ("nanori", j2c, None),
    ("meanings", j2c, None),
    ("frequency_rank", _, None),
    ("grade", _, None),
    ("jlpt", _, None),
    ("kanken", _, None),
    ("primitives", _, None),
    ("primitive_of", _, None),
    ("primitive_keywords", j2c, None),
    ("primitive_alternatives", _, None),
    ("heisig_id5", _, None),
    ("heisig_id6", _, None),
    ("heisig_keyword5", _, None),
    ("heisig_keyword6", _, None),
    ("heisig_story", _, None),
    ("heisig_comment", _, None),
    ("radicals", list, None),
    ("words_default", _, None),
    ("koohi_stories", j2c, None),
    ("wk", _, None),
    ("usr_keyword", _, "usr.keywords.usr_keyword"),
    ("usr_primitive_keyword", _, "usr.keywords.usr_primitive_keyword"),
    ("usr_story", _, "usr.stories.usr_story"),
]



search_options = [
     ['a',  'all', ],
     ['c',  'character', ],
     ['sc', 'stroke_count', ],
     ['oy', 'onyomi', ],
     ['ky', 'kunyomi', ],
     ['',   'nanori', ],
     ['m',  'meanings', ],
     ['fr',  'frequency_rank', ],
     ['g',  'grade', ],
     ['',   'jlpt', ],
     ['ka',  'kanken', ],
     ['p',  'primitives', ],
     ['pk', 'primitive_keywords', ],
     ['pa', 'primitive_alternatives', ],
     ['h5', 'heisig_id5', ],
     ['h6', 'heisig_id6', ],
     ['hk5','heisig_keyword5', ],
     ['hk6','heisig_keyword6',], 
     ['hk', 'heisig_keyword', ],
     ['k', 'keyword', ],
     ['hs', 'heisig_story', ],
     ['hc', 'heisig_comment', ],
     ['r',  'radicals',],
     ['wd', 'words_default', ],
     ['ks',  'koohi_stories', ],
     ['po', 'primitive_of', ],
     ['',   'wk', ],
     ['uk','usr_keyword',],
     ['upk','usr_primitive_keyword',],
     ['us','usr_story',],

]

search_values = dict()


def get_long_name(given_option):
    for option in search_options:
        if given_option == option[0]:
            return option[1]
    return given_option


class VerboseStore(argparse.Action):
    
    def __call__(self, parser, namespace, values, option_string=None):
        field = get_long_name(option_string[1:])
        print(f"Storing {values} in the {field} option...")
        setattr(namespace, self.dest, values)
        if field in search_values:
            search_values[field] += values
        else:
            search_values[field] = values

parser = argparse.ArgumentParser(
    prog="db_search",
    description="Search kanji.db using regex",
     
)

general = parser.add_argument_group("general parameters")

general.add_argument('-db', '--db_path', action="store", default=DEFAULT_KANJI_DB_PATH)
general.add_argument('-udb', '--user_db_path', action="store", default=DEFAULT_USER_DB_PATH)
general.add_argument('-or', '--or_logic', action="store_true")
general.add_argument('-cs', '--case_sensitive', action="store_true")
general.add_argument('-re', '--regex', action="store_true")
general.add_argument('-f', '--format', default="tsv")
general.add_argument('-of', '--output_file')
general.add_argument('-lr', '--list_radicals',action="store_true")
general.add_argument('-lp', '--list_primitives',action="store_true")
general.add_argument('-ap', '--analyze_primitives',action="store_true")

field_parameters = parser.add_argument_group("database field parameters")

for option in search_options:
    if option[0] != '':
        field_parameters.add_argument('-' + option[0], '--' + option[1], action=VerboseStore, nargs='*')
    else:
        field_parameters.add_argument('--' + option[1], action=VerboseStore, nargs='*')


format_options = ['tsv','csv','list']
numerical_fields = ['stroke_count','frequency_rank','kanken','heisig_id5','heisig_id6']

args = parser.parse_args()

if args.format not in format_options:
    format_str = args.format
    # de-escape tab
    format_str = re.sub("\\\\t","\\t",format_str)
    fmt_variables = re.findall('{([^}]+)}', format_str)
    format_variables = []
    for x in fmt_variables:
        lx =  get_long_name(x)
        if lx != x:
            format_str = re.sub('{' + x + '}', '{' + lx + '}', format_str)
        format_variables.append(lx)
    print("FORMAT VARIABLES:", format_variables)


print("ARGS: ",args)
print("SEARCH VALUES: ",search_values)

#exit(0)




db_path = os.path.abspath(args.db_path)

con = sqlite3.connect(db_path)
#con.row_factory = sqlite3.Row
crs = con.cursor()
crs.execute(f'ATTACH DATABASE "{args.user_db_path}" AS usr;')


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
default_tsv_field_conversion = [
    (0,"character", _, None),
    (1,"meanings", j2c, None),
    (2,"primitive_alternatives", _, None),
    (3,"primitives", _, None),
    (4,"heisig_keyword5", _, None),
    (5,"heisig_keyword6", _, None),
    (6,"primitive_keywords", j2c, None),
    (7,"heisig_story", _, None),
    (8,"heisig_comment", _, None),
    (9,"radicals", _, None),
]


fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

joins = [
    f"LEFT OUTER JOIN usr.keywords ON characters.character == usr.keywords.character ",
    f"LEFT OUTER JOIN usr.stories ON characters.character == usr.stories.character ",
]

joins_txt = "".join(joins)

crs.execute(
    f"SELECT {fields} FROM characters {joins_txt} "
)
#crs.execute("SELECT * FROM characters")
db_data = crs.fetchall()

column_names = [description[0] for description in crs.description]
field_idx = dict()
for idx in range(0,len(column_names)):
    field_idx[column_names[idx]] = idx
              
print("kanji.db column names:", column_names)

story = column_names.index('primitive_of')

primitive_cache = {}
radical_count = {}
primitive_count = {}


def does_match(needle, haystack):
    if haystack is None:
        haystack = ''
    if args.regex:
        if args.case_sensitive:
            if re.match(needle, haystack):
                return True
        else:
            if re.match(needle, haystack, re.IGNORECASE):
                return True
    else:
        if args.case_sensitive:
            if needle in haystack:
                return True
        else:
            if needle.lower() in haystack.lower():
                return True
    return False


def does_match_any(needle, haystacks_list):
    for haystack in haystacks_list:
        if haystack is not None:
            res = does_match(needle, haystack)
            if res:
                return True
    return False


def does_numerical_value_match(needle, haystack):
    if haystack is None:
        return False
    if needle[0:2] == '>=':
        int_v = int(needle[2:])
        if haystack >= int_v:
            return True
    elif needle[0:2] == '<=':
        int_v = int(needle[2:])
        if haystack <= int_v:
            return True
    elif needle[0] == '>':
        int_v = int(needle[1:])
        if haystack > int_v:
            return True
    elif needle[0] == '<':
        int_v = int(needle[1:])
        if haystack < int_v:
            return True
    else:
        int_v = int(needle)
        if int_v == haystack:
            return True
    return False





for raw_data in db_data:

    d = {}
    for data, (name, load_func, _) in zip(raw_data, requested_fields):
        d[name] = load_func(data)

    character = d['character']
    if args.list_radicals:
        for radical in d['radicals']:
            if radical not in radical_count:
                radical_count[radical] = 1
            else:
                radical_count[radical] += 1
    primitive_cache[character] = custom_list(d['primitives'])

    if args.list_primitives or args.analyze_primitives:
        primitives_of = custom_list(d['primitive_of'])
        if len(primitives_of) > 0:
            if character not in primitive_count:
                primitive_count[character] = len(primitives_of)
            else:
                primitive_count[character] += len(primitives_of)

    if args.or_logic:
        # search using OR logic
        found=False
        for field, values in search_values.items():
            for value in values:
                if field == 'all':
                    all_fields = [str(x) for x in d.values()]
                    all_fields_str = ' '.join(all_fields)
                    if does_match(value, all_fields_str):
                        found = True
                elif field == 'heisig_keyword':
                    hk5 = d['heisig_keyword5']
                    hk6 = d['heisig_keyword6']
                    if does_match_any(value, [hk5, hk6]):
                        found = True
                elif field == 'keyword':
                    hk5 = d['heisig_keyword5']
                    hk6 = d['heisig_keyword6']
                    pk = d['primitive_keywords']
                    uk = d['usr_keyword']
                    upk = d['usr_primitive_keyword']
                    if does_match_any(value, [hk5, hk6, pk, uk, upk]):
                        found = True
                elif field in numerical_fields:
                    v = d[field]
                    if does_numerical_value_match(value,v):
                        found = True
                else:
                    v = d[field]
                    if does_match(value, v):
                        found = True
    else:
        ### search using AND logic
        found = True
        for field, values in search_values.items():
            for value in values:
                if field == 'all':
                    all_fields = [str(x) for x in d.values()]
                    all_fields_str = ' '.join(all_fields)
                    if not does_match(value, all_fields_str):
                        found = False
                elif field == 'heisig_keyword':
                    hk5 = d['heisig_keyword5']
                    hk6 = d['heisig_keyword6']
                    if not does_match_any(value, [hk5, hk6]):
                        found = False
                elif field == 'keyword':
                    hk5 = d['heisig_keyword5']
                    hk6 = d['heisig_keyword6']
                    pk = d['primitive_keywords']
                    uk = d['usr_keyword']
                    upk = d['usr_primitive_keyword']
                    if character == '亜':
                        print("fsdfds")
                    if not does_match_any(value, [hk5, hk6, pk, uk, upk]):
                        found = False
                elif field in numerical_fields:
                    v = d[field]
                    if not does_numerical_value_match(value,v):
                        found = False
                else:

                    v = d[field]
                    if not does_match(value, v):
                        found = False

    if found and len(search_values)>0:
        if args.format == 'tsv':

            tsv_d = []

            for (_, name, load_func, _) in default_tsv_field_conversion:
                tsv_d.append( load_func(raw_data[field_idx[name]]) or '')
            #for (_, name, load_func, _) in default_tsv_field_conversion:
            #    tsv_d.append( d[name])

            """
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
            """
            res = fw(tsv_d)
            print(res)
            print("")
        elif args.format == 'list':
            for options in search_options:
                field = options[1]
                if field == 'heisig_keyword':
                    continue
                v = d[field]
                print("\t%s:%s" % (field.ljust(20),v))
            print("")
        else:
            # formatted output
            output_str = format_str
            for variable in format_variables:
                v = d[variable]
                if v is None:
                    v = ''
                if isinstance(v, int):
                    v = str(v)
                if isinstance(v, list):
                    v = ','.join(v)
                output_str = re.sub('{' + variable + '}', v, output_str)
            
            print(output_str)

            #formatted_str = format_str.format(**variables)

if args.list_radicals:
    print("#### RADICALS #####")
    sorted_radical_count = dict(sorted(radical_count.items(), key=lambda x:x[1]))
    for radical in sorted_radical_count:
        print("%s\t%d" % (radical, radical_count[radical]))

sorted_primitives_count = dict(sorted(primitive_count.items(), key=lambda x:x[1], reverse=True))
if args.list_primitives:
    print("#### PRIMITIVES #####")
    for primitive in sorted_primitives_count:
        print("%s\t%d" % (primitive, primitive_count[primitive]))


def find_all_primitives(character, recursive=True):
    primitives = primitive_cache[character]
    if len(primitives) == 1 and primitives[0] == character:
        return set()
    found_primitives = set(primitives)
    if recursive:
        for p in primitives:
            if p != character:
                found_primitives |= find_all_primitives(p)
    return set(found_primitives)

def find_kanjis_using_primitives( target_primitive_set, recursive=False):

    matched_kanjis = []
    for character in primitive_cache.keys():
        primitive_set = find_all_primitives(character,recursive)

        if target_primitive_set.issubset(primitive_set):
            matched_kanjis.append(character)
    return matched_kanjis


def find_existing_primitive( target_primitive_set ):
    for character in primitive_cache.keys():
        primitive_set = find_all_primitives(character)
        if target_primitive_set == primitive_set:
            return character
    return None



if args.analyze_primitives:
    primitives = list(sorted_primitives_count.keys())
    for i in range(len(primitives)):
        p_a = primitives[i]
        a_primitives = find_all_primitives(p_a) | set(p_a)
        if i < len(primitives) - 1:
            for j in range(i+1,len(primitives)):
                p_b = primitives[j]
                b_primitives = find_all_primitives(p_b) | set(p_b)

                if (a_primitives.issubset(b_primitives) or b_primitives.issubset(a_primitives)):
                    continue
                else:
                    common_primitive_set = a_primitives | b_primitives
                    existing_primitive = find_existing_primitive(common_primitive_set)
                    if existing_primitive is not None:
                        #print("%s + %s: Skipping %s" % (p_a,p_b,existing_primitive))
                        pass
                    else:
                        kanjis = find_kanjis_using_primitives( set([p_a, p_b]), recursive=False)
                        if len(kanjis) > 2:
                            print("%s + %s: %s" % (p_a,p_b, ', '.join(kanjis)))
 
con.close()