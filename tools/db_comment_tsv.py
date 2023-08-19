import sqlite3
import json
import sys
import os
import re

raise Exception("Fix not adding <b> or <i> inside [] !!")

verbose = False  # If not true, print out only new cards and changes

# Creates a list of single-character Unicode kanjis and [primitive] tags
# For example '[banner]也' -> ['\[banner\]','也'] 
def custom_list(l):
    g = re.findall(r'([^\[]|\[[^\]]+\])',l)
    return g


def replace(match,tag):
    #print(match.string)
    #for m in match.groups():
    #    print(':',m)
    res = ''
    if match.group(1) is not None:
        res += match.group(1)
    if match.group(2) is not None:
        res += match.group(2)
    if match.group(1) is None:
        res += '<' + tag + '>' + match.group(3) + '</' + tag + '>'
    else:
        res += match.group(3)
    if match.group(4) is not None:
        res += match.group(4)
    if match.group(5) is not None:
        res += match.group(5)
    return res


def replace_i(match):
    return replace(match,'i')


def replace_b(match):
    return replace(match,'b')


test = 'The primitive meaning, genie, derives from the roots of the word genius. Use the genie out in the open when the primitive appears to the right of or below its relative primitive; in that case it also keeps its same form. At the left, the form is altered to [genie_in_the_bottle], and the meaning becomes a genie in the bottle.'



reg = '([^\]]*\[)([a-zA-Z\-_]+)(\][^\]]*)'

new_test = re.sub(reg,'\1<img \2>\3',test,flags=re.IGNORECASE)

test ='<i>A banner</i> . . . <i>a zoo</i>. Hint: think of a merry-go-round.'
prim_keyword = 'banner'
reg = r'(<[^>/]+>)*([^<]*)(' + prim_keyword +')([^<]*)(</[^>]+>)*'
target = r' <i>\1</i>'


test4 ='<i> A banner</i> banner . . . <i>a zoo</i>. banner Hint: think of a merry-go-round.'
new_test4 = re.sub(reg,replace_b,test4,flags=re.IGNORECASE)

new_test = re.sub(reg,replace_b,test,flags=re.IGNORECASE)

test2 ='A banner . . . <i>a zoo</i>. Hint: think of a merry-go-round.'
new_test2 = re.sub(reg,replace_b,test2,flags=re.IGNORECASE)

test3 ='banner . . . <i>a zoo</i>. Hint: think of a merry-go-round.'
new_test3 = re.sub(reg,replace_b,test3,flags=re.IGNORECASE)


#test = '[spear]帚ヨ[apron]'
#test2 = 'a[banner]也[b]'

#l = custom_list(test)
#l2 = custom_list(test2)

output_tsv_path = "addon/kanji-ext-clean.tsv"
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

update_fields = fields[1:]

insert_sql = (
    f'INSERT OR IGNORE into characters ({",".join(fields)}) values ({",".join("?"*len(fields))})'
)
update_sql = (
    f'UPDATE characters SET {"=? , ".join(update_fields)}=? WHERE character=?'
)
update_prim_of_sql = (
    f'UPDATE characters SET primitive_of=? WHERE character=?'
)

def to_json_list_str(csv):
    if csv!= '':
        item_list = csv.split(',')
        clean_list = [item.strip() for item in item_list]
        return json.dumps(clean_list)
    return '[]'


# (field_name, load_function, column)
_ = lambda x: x
field_conversion = [
    (0,"character", _, None),
    (1,"meanings", to_json_list_str, None),
    (2,"primitive_alternatives", _, None),
    (3,"primitives", _, None),
    (4,"heisig_keyword5", _, None),
    (5,"heisig_keyword6", _, None),
    (6,"primitive_keywords", to_json_list_str, None),
    (7,"heisig_story", _, None),
    (8,"heisig_comment", _, None),
    (9,"radicals", _, None),
]



##################################################################
print("Reconstructing kanji name lookup table..")

crs.execute("SELECT * FROM characters")
data = crs.fetchall()

column_names = [description[0] for description in crs.description]
print("kanji.db column names:", column_names)

poi = column_names.index('primitive_of')
pi = column_names.index('primitives')
ci = column_names.index('character')
ri = column_names.index('radicals')
fi = column_names.index('frequency_rank') 
mi = column_names.index('meanings') 
hk5i = column_names.index('heisig_keyword5') 
hk6i = column_names.index('heisig_keyword6') 
pki = column_names.index('primitive_keywords') 

primitive_of_dict = dict()

kanji_names = dict()

# Create a lookup table for kanji names
for row in data:
    character = row[ci]
    character = character.replace('[','')
    character = character.replace(']','')
    #if character[0] != '[':
    #    continue
    #if character != '[arm]':
    #    continue
    primitives = custom_list(row[pi])

    #names = json.loads(row[mi])
    names = []
    if row[hk5i] is not None:
        names += row[hk5i].split(',')
    if row[hk6i] is not None:
        names += row[hk6i].split(',')
    if row[pki] is not None:
        names += json.loads(row[pki]) # row[pki].split(',')

    names = [name.strip() for name in names if name != '']
    names = [name.replace('[','') for name in names]
    names = [name.replace(']','') for name in names]
    names = set(names)

    kanji_names[character] = names
    



############

processed_kanji_list = []

header = []


test = 'Notice how these <b>human legs</b> are somewhat shapelier and <i>somewhat</i> more highly evolved than those of the so-called “lower animals.” The one on the left, drawn first, is straight; while the one on the right bends gracefully and ends with a hook. Though they are not likely to suggest the legs of any human you know, they do have something of the look of someone out for a stroll, especially if you compare them to <i>animal legs</i>. If you had any trouble with the kanji for the number four, now would be the time to return to it (frame 4). [2]'

kw = 'somewhat'

res = re.sub('[^>]' + kw,'<b>' + kw + '</b>',test)

#res2 = re.sub('somewhat','<b>somewhat</b>',test)

f_o = open(output_tsv_path,'w', encoding='utf-8')


for l in open(ext_tsv_path, "r", encoding="utf-8"):
    d = l.replace("\n", "").split("\t")
    if len(d[0]) == 0:
        print(l.replace("\n", ""), file=f_o)
        f_o.flush()
        continue
    if d[0] == 'Kanji':
        header = d
        hs_i = d.index('Heisig Story')
        hc_i = d.index('Heisig Comment')
        p_i = d.index('Primitives')
        m_i = d.index('Meanings')

        hk5_i = d.index('Heisig Keyword (1-5)')
        hk6_i = d.index('Heisig Keyword (6+)')
        pw_i = d.index('Primitive Keywords')
        print(l.replace("\n", ""), file=f_o)                       
        continue
    if d[0][0]=='#':  # omit the comments
        print(l.replace("\n", ""), file=f_o)                       
        continue

    if len(d) != 10:
        raise Exception("Error! Wrong length in data: %s" % str(d))

    kanji = d[0].strip()

    if kanji in processed_kanji_list:
        raise Exception("Kanji %s already processed! Remove duplicate" % kanji)
    processed_kanji_list.append(kanji)

    print("Processing", kanji, d[1])

    meanings = d[m_i].split(', ')
    pws = d[pw_i].split(', ')
    pws = [pw.replace('[','') for pw in pws]
    pws = [pw.replace(']','') for pw in pws]
    keywords = list(set([d[hk5_i], d[hk6_i]] + pws ))
    keywords = [kw for kw in keywords if kw != '']

    h_story = d[hs_i]
    h_comment = d[hc_i]

    new_h_story = h_story
    new_h_comment = h_comment


    for keyword in keywords:
        reg = r'(<[^>/]+>)*([^<]*)(' + keyword +')([^<]*)(</[^>]+>)*'

        new_h_story = re.sub(reg,replace_b,new_h_story,flags=re.IGNORECASE)
        new_h_comment = re.sub(reg,replace_b,new_h_comment,flags=re.IGNORECASE)

    primitives = d[p_i]
    primitives = custom_list(primitives)
    prim_keywords = []
    for prim in primitives:
        prim = prim.replace('[','')
        prim = prim.replace(']','')

        for prim_keyword in kanji_names[prim]:
            if prim_keyword not in prim_keywords:
                prim_keywords.append(prim_keyword)
    for prim_keyword in prim_keywords:
        reg = r'(<[^>/]+>)*([^<]*)(' + prim_keyword +')([^<]*)(</[^>]+>)*'
        new_h_story = re.sub(reg,replace_i,new_h_story,flags=re.IGNORECASE)
        new_h_comment = re.sub(reg,replace_i,new_h_comment,flags=re.IGNORECASE)

    if h_story != new_h_story:
        print(h_story)
        print(new_h_story)
        print("")
        d[hs_i] = new_h_story
        d[hc_i] = new_h_comment

    new_l = '\t'.join(d)
    print(new_l, file=f_o)

con.close()
f_o.close()
