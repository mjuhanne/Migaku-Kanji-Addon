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
    ("stroke_count", _, None),
    ("sec_primitives", _, None),
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

kanji_parent_candidate = dict()
kanji_stroke_count = dict()

kanji_ref_count = dict()

for row in rows:

    c = row[0]
    prim = row[3]
    prim = custom_list(prim)
    sec_p = custom_list(row[12])
    h_id = row[10]
    sc = row[11]

    for p in prim:
        if p not in kanji_ref_count:
            kanji_ref_count[p] = 1
        else:
            kanji_ref_count[p] += 1
    for p in sec_p:
        if p not in kanji_ref_count:
            kanji_ref_count[p] = 1
        else:
            kanji_ref_count[p] += 1



    if c == "葉":
        print("fsd")
    kanji_id[c] = h_id
    kanji_primitives[c] = prim + sec_p
    kanji_stroke_count[c] = sc


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
    

    if c in kanji_ref_count:
        if kanji_ref_count[c] < 3:
            not_found_name = '_' + not_found_name
        if kanji_ref_count[c] < 2:
            not_found_name = '_' + not_found_name
    else:
        not_found_name = '_x_' + not_found_name

    if not os.path.exists(svg_path):
        supp_svg_path = "addon/kanjivg-supplementary/" + svg_name
        if not os.path.exists(supp_svg_path):

            print(c,"not found")
            supp_svg_path = "addon/kanjivg-supplementary/" + not_found_name
            if parent_svg_path is not None:
                if c not in kanji_parent_candidate:
                    kanji_parent_candidate[c] = parent
                    copyfile(kanji_name, alphabet_name, parent, parent_alphabet_name, parent_svg_path,supp_svg_path)
                else:
                    if kanji_stroke_count[parent] < kanji_stroke_count[kanji_parent_candidate[c]]:
                        print("---",c,": ",parent,"is better than", kanji_parent_candidate[c])
                        kanji_parent_candidate[c] = parent
                        copyfile(kanji_name, alphabet_name, parent, parent_alphabet_name, parent_svg_path,supp_svg_path)
            else:
                print("Even parent %s of %s kanjivg not found!" % (parent,c))
            svg_path = None
    processed_kanji[c] = c

    for p in kanji_primitives[c]:
        #if p not in processed_kanji:
        if p != c:
            check_recursively_kanjivg(p, c, alphabet_name, svg_path)
    


for c in kanji_primitives:
    if kanji_id[c] is not None:
        check_recursively_kanjivg(c, None, None, None)

