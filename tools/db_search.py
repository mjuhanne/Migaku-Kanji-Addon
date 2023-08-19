import sqlite3
import json
import sys
import os
import re
import argparse
import logging

DEFAULT_KANJI_DB_PATH = "addon/kanji.db"
DEFAULT_USER_DB_PATH = "addon/user_files/user.db"

# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g

def tsv(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    return "\t".join(args)

def csv(args):
    return ",".join(args)



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
    #("radicals", list, None),
    ("radicals", _, None),
    ("words_default", _, None),
    ("koohi_stories", j2c, None),
    ("wk", _, None),
    ("usr_keyword", _, "usr.keywords.usr_keyword"),
    ("usr_primitive_keyword", _, "usr.keywords.usr_primitive_keyword"),
    ("usr_story", _, "usr.stories.usr_story"),
]

def get_formatter_for_field(field_name):
    for (field, formatter, _notused) in requested_fields:
        if field_name == field:
            return formatter
    raise Exception("Unknown field %s" % (field_name))

# (field_name, load_function, column)
"""
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
"""

csv_quoted_fields = ["meanings","primitive_keywords","onyomi","kunyomi","nanori","meanings",
                     "koohi_stories", "heisig_story", "heisig_comment", 
                     "usr_keyword", "usr_primitive_keyword", "usr_story" ]


default_tsv_output_fields = ["character","meanings", "primitive_alternatives",
    "primitives","heisig_keyword5","heisig_keyword6","primitive_keywords", 
    "heisig_story","heisig_comment","radicals" ]



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
            if args.double:
                if haystack.count(needle) == 2:
                    return True
            else:
                if needle in haystack:
                    return True
        else:
            if args.double:
                if haystack.lower().count(needle.lower()) == 2:
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


############ Command line argument related stuff ##################################

def get_long_name(given_option):
    for option in search_options:
        if given_option == option[0]:
            return option[1]
    return given_option

class VerboseStore(argparse.Action):
    
    def __call__(self, parser, namespace, values, option_string=None):
        field = get_long_name(option_string[1:])
        setattr(namespace, self.dest, values)
        if field in search_terms:
            search_terms[field] += values
        else:
            search_terms[field] = values


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
     ['ra',  'radicals',],
     ['wd', 'words_default', ],
     ['ks',  'koohi_stories', ],
     ['po', 'primitive_of', ],
     ['',   'wk', ],
     ['uk','usr_keyword',],
     ['upk','usr_primitive_keyword',],
     ['us','usr_story',],

]

search_terms = dict()

parser = argparse.ArgumentParser(
    prog="db_search",
    description="Search kanji.db using regex",
     
)

general = parser.add_argument_group("general parameters")

general.add_argument('-db', '--db_path', action="store", default=DEFAULT_KANJI_DB_PATH)
general.add_argument('-udb', '--user_db_path', action="store", default=DEFAULT_USER_DB_PATH)
general.add_argument('-or', '--or_logic', action="store_true")
general.add_argument('-s', '--sort', action="store")
general.add_argument('-r', '--reverse', action="store_true")
general.add_argument('-cs', '--case_sensitive', action="store_true")
general.add_argument('-2', '--double', action="store_true")
general.add_argument('-re', '--regex', action="store_true")
general.add_argument('-f', '--format', default="tsv")
general.add_argument('-of', '--output_file')
general.add_argument('-v', '--verbose', action="store_true")
general.add_argument('-t', '--testing', action="store_true")

field_parameters = parser.add_argument_group("database field parameters")

for option in search_options:
    if option[0] != '':
        field_parameters.add_argument('-' + option[0], '--' + option[1], action=VerboseStore, nargs='*')
    else:
        field_parameters.add_argument('--' + option[1], action=VerboseStore, nargs='*')


format_options = ['tsv','csv','markdown','list']
numerical_fields = ['stroke_count','frequency_rank','kanken','heisig_id5','heisig_id6']

args = parser.parse_args()

if args.verbose:
    print("ARGS: ",args)
    print("SEARCH TERMS: ",search_terms)

if args.testing:
    search_terms = {'heisig_id6' : ['>2000','<3000'], 'heisig_keyword6': ['^$']}
    args.regex = True

############# Open both main and user databases ###########

db_path = os.path.abspath(args.db_path)

con = sqlite3.connect(db_path)
#con.row_factory = sqlite3.Row
crs = con.cursor()
crs.execute(f'ATTACH DATABASE "{args.user_db_path}" AS usr;')

fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

joins = [
    f"LEFT OUTER JOIN usr.keywords ON characters.character == usr.keywords.character ",
    f"LEFT OUTER JOIN usr.stories ON characters.character == usr.stories.character ",
]

joins_txt = "".join(joins)

crs.execute(
    f"SELECT {fields} FROM characters {joins_txt} "
)
db_data = crs.fetchall()

column_names = [description[0] for description in crs.description]
field_idx = dict()
for idx in range(0,len(column_names)):
    field_idx[column_names[idx]] = idx
              
if args.verbose:
    print("kanji.db column names:", column_names)

valid_output_field_names = column_names + ['heisig_keyword', 'keyword']

####### Output formatting #########################

# Parse --format string
format_option = "custom" # default
for option in format_options:
    ol = len(option)
    if len(args.format) >= ol:
        if args.format[:ol] == option:
            format_option = option
            if len(args.format) > ol:
                if args.format[ol] != ':':
                    print("Error in --format parameter. Should be e.g.: --format csv:character,heisig_keyword,heisig_story")
                    exit(0)
                else:
                    fields = args.format[ol+1:]
                    if fields == '*':
                        # select all available fields
                        format_output_fields = column_names
                    else:
                        format_output_fields = fields.split(',')
                        format_output_fields = [get_long_name(x) for x in format_output_fields if x != '']
                        if len(format_output_fields) == 0:
                            print("Error in --format output option. No fields selected!")
                            exit(0)
                        for field in format_output_fields:
                            if field not in valid_output_field_names:
                                print("Error in --format output option. Invalid field '%s'" % field)
                                exit(0)
            else:
                # no fields given. TSV has its own default fields. For CSV/Markdown/list all fields will be output
                if option == 'tsv':
                    format_output_fields = default_tsv_output_fields
                else:
                    format_output_fields = column_names
        

if format_option == 'custom':
    # custom output formatting

    format_option = "custom"
    format_str = args.format
    # de-escape tab and newline
    format_str = re.sub("\\\\t","\\t",format_str)
    format_str = re.sub("\\\\n","\\n",format_str)
    fmt_variables = re.findall('{([^}]+)}', format_str)
    format_variables = []
    for x in fmt_variables:
        lx =  get_long_name(x)
        if lx != x:
            format_str = re.sub('{' + x + '}', '{' + lx + '}', format_str)
        format_variables.append(lx)
    if args.verbose:
        print("FORMAT VARIABLES:", format_variables)

###### Output file and logging ###############################

if args.output_file:
    targets = logging.StreamHandler(sys.stdout), logging.FileHandler(args.output_file,'w+')
else:
    targets = logging.StreamHandler(sys.stdout),

logging.basicConfig(format='%(message)s', level=logging.INFO, handlers=targets)


header = ''
if format_option == 'csv':
    header = ','.join(format_output_fields)
elif format_option == 'tsv':
    header = '\t'.join(format_output_fields)
elif format_option == 'markdown':
    header = '| ' + ' | '.join(format_output_fields) + ' |\r\n'
    for f in format_output_fields:
        header += '|--'
    header += '|'

if header != '':
    logging.info(header)

########### Search ###################################

if args.sort:
    unsorted_lines = dict()
    sort_field = get_long_name(args.sort)

match_count = 0

for raw_data in db_data:

    d = {}
    for data, (name, load_func, _) in zip(raw_data, requested_fields):
        d[name] = load_func(data)

    character = d['character']

    if args.or_logic:
        # search using OR logic
        found=False
        for field, values in search_terms.items():
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
        for field, values in search_terms.items():
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

    if found:
        match_count += 1

        if format_option == 'tsv':
            tsv_d = []
            for field in format_output_fields:
                tsv_d.append(str(d[field] or ''))
            res = tsv(tsv_d)

        elif format_option == 'csv':
            csv_d = []
            for field in format_output_fields:
                item = str(d[field] or '')
                if field in csv_quoted_fields:
                    item = '"' + item + '"'
                csv_d.append(item)
            res = csv(csv_d)
        elif format_option == 'markdown':
            res = '| '
            for field in format_output_fields:
                res += (str(d[field] or '' )) + ' | '
        elif format_option == 'list':
            res = ''
            for field in format_output_fields:
                v = str(d[field] or '')
                line = "\t%s:%s\r\n" % (field.ljust(20),v)
                res += line 
        else:
            # formatted output
            res = format_str
            for variable in format_variables:
                v = d[variable]
                if v is None:
                    v = ''
                if isinstance(v, int):
                    v = str(v)
                if isinstance(v, list):
                    v = ','.join(v)
                res = re.sub('{' + variable + '}', v, res)

        if not args.sort:
            logging.info(res)
        else:
            # save for later sorting
            unsorted_lines[d[sort_field]] = res

if args.sort:
    if args.reverse:
        sorted_lines = sorted(unsorted_lines.items(), reverse=True)
    else:
        sorted_lines = sorted(unsorted_lines.items())
    sorted_lines = list(dict(sorted_lines).values())
    for line in sorted_lines:
        logging.info(line)

con.close()

print("Match count: %d" % match_count)
