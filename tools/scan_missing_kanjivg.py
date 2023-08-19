import sqlite3
import json
import sys
from collections import OrderedDict
import os
import re
import shutil

def j2c(d):
    return ", ".join(json.loads(d))

# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g


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
    ("heisig_id6", _, None),
]


kanji_db_path = sys.argv[1] if len(sys.argv) > 1 else "addon/kanji.db"

con = sqlite3.connect(kanji_db_path)
crs = con.cursor()

fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

crs.execute(
    f"SELECT {fields} FROM characters"
)
rows = crs.fetchall()

db_data = dict()

processed_kanji = dict()

kanji_primitives = dict()
kanji_id = dict()

for row in rows:

    c = row[0]
    p = row[3]
    p = custom_list(p)
    h_id = row[10]
    kanji_id[c] = h_id
    kanji_primitives[c] = p

def copyfile(c, alphabet_name, parent, parent_alphabet_name, input,output):
    fo = open(output,"w",encoding="utf-8")
    with open(input,"r",encoding="utf-8") as fi:
        lines = [line.rstrip().replace(parent_alphabet_name,alphabet_name) for line in fi]
        l2 = f'<g id="kvg:StrokePaths_%s" style="fill:none;stroke:#000000;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;">' % alphabet_name
        l3 = f'<g id="kvg:%s" kvg:element="%s">' % (alphabet_name,c)
        lines[1] = l2
        lines[2] = l3
        data = '<!-- Targeting %s from original %s -->\n' % (c,parent)

        fo.write(data)
        data = '\n'.join(lines)
        fo.write(data)
    fo.close()



def check_recursively_kanjivg(c, parent,parent_alphabet_name,  parent_svg_path):
    if c[0] == '[':
        not_found_name = '_' + c[1:-1] + ".svg"
        svg_name = c[1:-1] + ".svg"
        svg_path = "addon/kanjivg/" + svg_name
        alphabet_name = c[1:-1]
        kanji_name = alphabet_name
    else:
        not_found_name = '_' + "%05x.svg" % ord(c)
        svg_name = "%05x.svg" % ord(c)
        svg_path = "addon/kanjivg/" + svg_name
        alphabet_name = "%05x" % ord(c)
        kanji_name = c

    if not os.path.exists(svg_path):
        print(c,"not found")
        supp_svg_path = "addon/kanjivg-supplementary/" + not_found_name
        if parent_svg_path is not None:
            copyfile(kanji_name, alphabet_name, parent, parent_alphabet_name, parent_svg_path,supp_svg_path)
        else:
            print("Even parent %s of %s kanjivg not found!" % (parent,c))
        svg_path = None
    processed_kanji[c] = c

    for p in kanji_primitives[c]:
        if p not in processed_kanji:
            check_recursively_kanjivg(p, c, alphabet_name, svg_path)
    


for c in kanji_primitives:
    if kanji_id[c] is not None:
        check_recursively_kanjivg(c, None, None, None)

