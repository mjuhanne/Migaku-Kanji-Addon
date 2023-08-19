import sqlite3
import json
import sys
import os
import re
#
# A tool to extract user modified fields and output them to a .tsv patch file
#

# When two characters reference each other as alternatives (for example 艹 -> 艸 and 艸 -> 艹 )
# then we want to link to the character which is the primary primitive
primary_primitives = ['艹','扌','⻖','⻏','川','罒','冫',]

primitive_alternative_cache = dict()

"""
 #nämä alternatiiveina?
'戶' : '', # 棨戾牖扃扂帍扁启扆晵肈戽昈戹肁魲妒扄馿
'靑' : '', # 靜箐睛鶄倩靘菁凊綪靚棈蜻猜婧䑶鼱崝靛圊靕靗

 # uudet primitiivit?
'㐱' : '', # 疹袗眕沴畛聄翏胗紾參跈趁殄昣軫
'炏' : '', # 瑩榮營煢滎勞熒㷀犖燚禜嫈焱縈塋螢鶯嵤罃焭謍膋檾鎣
'㐌' : '', # 沲陁拖迤絁鉇駞袘柂
'吿' : '', # 晧窖焅鵠悎梏誥捁硞靠牿嚳郜哠俈
'㚇' : '', # 糉嵕稯騣緵葼鬉鬷椶鍐
'歲' : '', # 翽濊穢噦薉奯顪劌獩鱥
'彥' : '', # 嵃顏喭偐遃
'龰' : '', # 緃從辵疋嚔懥
'亏' : '', # 夸雩咢圬杇
'兹' : '', # 孳鎡鶿鷀糍禌
'㓞' : '', # 恝栔齧挈絜洯
'益' : '', # 塧隘謚鎰縊艗搤嗌蠲鷁螠
'䖵' : '', # 蠢蠧蠹蟸螙蟲蠶蠡螽蝨蠺蟁蠭蝱蟊蠚
'吅' : '', # 雚僉嚴咒咢賷單斝哭襄囊
'旣' : '', # 摡墍廐曁蔇嘅
'產' : '', # 滻鏟剷
'卝' : '', # 哶虁羐羋
'遀' : '', # 膸隨髓
'㕓' : '', # 纒壥
'巂' : '', # 攜蠵觿
'臯' : '', # 嘷翺皥
'䧹' : '', # 譍膺
'吳' : '', # 俁蜈茣悞麌鋘
'㗊' : '', # 器囂噐噩嚚

'欮' : '', # 厥闕
'㡭' : '', # 繼斷
'盇' : '', # 葢豓
'絭' : '', # 縢勬
'叹' : '', # 凾焏
'䩭' : '', # 羇覉
'㽞' : '', # 嘼鼉
'羕' : '', # 樣漾
'䀠' : '', # 瞾瞿
'罙' : '', # 賝琛
'巜' : '', # 粼兪
'㞢' : '', # 蚩旹
'乡' : '', # 鄕雍
'㼌' : '', # 寙蓏窳
'䩻' : '', # 羈覊
'龱' : '', # 囟鬛巤
'㐭' : '', # 啚禀稟亶
'仌' : '', # 俎睂蕐

"""

primitive_correction = {

'⺽' : '臼', # 學與鷽盥黌礐鱟夓爨璺覺嚳釁
'龹' : '[quarter]', # 鮝畻弮䅈黱媵眷塍漛䄅卷賸劵桊滕豢
'⺈' : '勹', # 焔厃麁夐臽
'狊' : '目犬', # 闃鶪湨
'巿' : '市', # 沛鬧閙旆杮芾伂鈰
'㐅' : '乂', # 恡罓爻鑁殺肴网儍鹵郄
'龺' : '𠦝', # 乹戟倝斡榦翰
'亚' : '亚', # 垩
'豖' : '豕', # 硺瘃涿椓啄琢冢諑
'內' : '内', # 吶
'处' : '夂人', # 昝咎
'厉' : '厂万', # 砺蛎
'雔' : '隹隹', # 靃犨雙讐

'益' : '益', 
'乛' : '', # 壽疋虍
'圼' : '日土', # 涅捏
'㝁' : '旬子', # 賯惸箰
'⺄' : '乙', # 虱丮
'煔' : '', # 檆
'龵' : '', # 拜
'㐄' : 'ヰ', # 舝夅
'頹' : '', # 㿗
'查' : '', # 猹
'㿟' : '', # 皛
'珤' : '', # 寶
'㬱' : '', # 濳
'亩' : '', # 畒
'㣎' : '泉彡', # 穆
'䲨' : '工鳥', # 鴻
'隡' : '⻖産', # 薩
'倠' : '人隹', # 雁
'砳' : '', # 磊
'㚒' : '', # 陝
'䌛' : '', # 邎
'㕡' : '', # 壑
'醀' : '', # 蘸
'㳄' : '', # 盜
'㩅' : '', # 籒
'沝' : '', # 淼
'㧜' : '', # 箍
'萈' : '', # 寬
'囬' : '', # 廽
'舋' : '', # 亹
'㞋' : '', # 赧
'龨' : '', # 滙
'曶' : '', # 匫
'㣊' : '', # 俢
'雐' : '', # 虧
'亐' : '', # 虧
'㐁' : '', # 弻
'䋰' : '目大糸', # 纂
'屖' : '', # 稺
'昛' : '', # 煚
'䲆' : '', # 鱻
'虽' : '', # 雖
'韰' : '', # 瀣
'粜' : '', # 糶
'㸚' : '爻爻', # 爾
'杀' : '', # 弑
'䦚' : '', # 濶
'閵' : '', # 藺
'眘' : '', # 傄
'䖭' : '', # 螣
'禼' : '', # 竊
'洰' : '', # 渠
'㦰' : '', # 韱
'㡯' : '', # 侂
'㕚' : '又丶丶', # 蚤
'賔' : '', # 濵
'夎' : '', # 蓌
'曅' : '', # 爗
'秃' : '', # 頽
'聑' : '', # 聶
'术' : '', # 殺
'畁' : '', # 腗
'㚅' : '', # 隆
'㢶' : '', # 弼
'翜' : '', # 㵤
'㞷' : '', # 匩
'媷' : '', # 薅
'㓣' : '', # 箚
'夃' : '', # 盈
'仑' : '', # 芲
'亾' : '', # 匃
'歨' : '', # 徙
'㕑' : '', # 櫉
'畂' : '', # 畞
'㚣' : '', # 姧
'⺌' : '', # 龸
'帣' : '', # 幐
'㿽' : '', # 諡
'稨' : '', # 藊
'軎' : '', # 毄
'啟' : '', # 闙
'戺' : '', # 焈
'⺻' : '', # 盡
'籴' : '', # 糴
'䊆' : '', # 毇
'㮊' : '', # 壄
'頝' : '', # 纐
'㓩' : '', # 葪
'义' : '', # 肞
'皂' : '', # 梍
'魝' : '', # 薊
'㚘' : '', # 輦
'㡿' : '', # 㴑
'䂞' : '', # 橐
'䩗' : '', # 霸
'牪' : '', # 犇
'㐫' : '', # 离
'駦' : '', # 儯
'䳡' : '', # 靍
'畣' : '', # 墖
'㲋' : '', # 毚
'䙴' : '', # 僊
'强' : '', # 繦
'刍' : '', # 煞
'䖒' : '', # 戲
'猌' : '', # 憖
'冧' : '', # 檾
'㹜' : '', # 猋
'㸒' : '', # 婬
'㲺' : '', # 柒
'类' : '', # 類
'敎' : '', # 漖
'鵭' : '', # 靎
'枀' : '', # 梥
'䙳' : '', # 樮
'䏌' : '', # 佾
'㘸' : '', # 塟
'竘' : '', # 蒟
'鍂' : '', # 鑫
}

def find_proper_primitive(p):
    # .. then reference the main primitive instead if this is an alternative primitive
    if p not in primary_primitives and p in primitive_alternative_cache:
        p = primitive_alternative_cache[p]

    if p in primitive_correction:
        if primitive_correction[p] != '':
            return primitive_correction[p]
    return p


user_modifiable_fields = ['primitives','primitive_keywords','heisig_story','heisig_comment']

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
tsv_path = sys.argv[3] if len(sys.argv) > 3 else "kanji-migaku-patch.tsv"

migaku_tsv_path = "migaku-kanji-db-2022-01-11-my.tsv"

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

column_names = [description[0] for description in crs.description]
print("kanji.db column names:", column_names)

p_i = column_names.index('primitives')
mod_p_i = column_names.index('mod_primitives')
c_i = column_names.index('character')
pa_i = column_names.index('primitive_alternatives')
fr_i = column_names.index('frequency_rank')
hi_i = column_names.index('heisig_id6')

hk5_i = column_names.index('heisig_keyword5')
hk6_i = column_names.index('heisig_keyword6')
pk_i = column_names.index('primitive_keywords')


new_primitives = dict()
kanji_primitives = dict()
kanji_line_numbers = dict()
kanji_keywords = dict()
kanji_ids = dict()

for row in rows:
    c = row[c_i]
    if c == '座':
        print("dsfr")
    prim = row[p_i]
    mod_prim = row[mod_p_i]
    if mod_prim is not None:
        prim = mod_prim
    prim_alt = row[pa_i]

    kanji_primitives[c] = prim
    if row[hi_i] is not None:
        kanji_ids[c] = row[hi_i]

    if c == "胥":
        print("sfdd")

    if row[hk5_i] is not None and row[hk5_i] != '':
        kanji_keywords[c] = row[hk5_i]
    elif row[hk6_i] is not None and row[hk6_i] != '':
        kanji_keywords[c] = row[hk6_i]
    elif row[pk_i] is not None and row[pk_i] != '[]':
        kanji_keywords[c] = row[pk_i]

    # create a reverse lookup table for primitive alternatives
    if len(prim_alt) > 0:
        prim_alt_list = custom_list(prim_alt)
        for p in prim_alt_list:
            primitive_alternative_cache[p] = c



f = open(tsv_path, "w", encoding="utf-8")

def fw(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    f.write("\t".join(args))
    f.write("\n")
    #print("\t".join(args))

# write header
fw( [
    "Kanji",
    "Field",
    "OldValue",
    "NewValue",
    "Comment",
]
)

unknown_primitives = dict()
total_unknown_occurrences = 0

line_number = 0
for l in open(migaku_tsv_path, "r", encoding="utf-8"):
    
    d = l.replace("\n", "").split("\t")
    line_number += 1

    character = d[0]
    new_primitives[character] = d[3]
    kanji_line_numbers[character] = line_number


crs.execute(
    f"SELECT {fields} FROM characters {joins_txt} ORDER BY heisig_id6 ASC"
)
rows = crs.fetchall()

for row in rows:

    c = row[c_i]
    id = row[hi_i]
    if id is not None:
        freq = row[fr_i]
        old_prim = kanji_primitives[c]

        if c not in new_primitives:
            print("Warning! %s couldn't be found in new Migaku excel" % c)
            continue
        new_prim = new_primitives[c]


        all_found = True
        proper_new_primitives = []
        missing_new_primitives = []
        for p in new_prim:
            p = find_proper_primitive(p)
            if len(p) == 1:
                if p not in kanji_primitives:
                    print("Warning! Unknown primitive %s for kanji %s at line number %d!" % (p,c,kanji_line_numbers[c]))
                    if p not in unknown_primitives:
                        unknown_primitives[p] = c
                    else:
                        unknown_primitives[p] += c
                    all_found = False
                    total_unknown_occurrences += 1
                    missing_new_primitives.append(p)
                else:
                    proper_new_primitives.append(p)
            else:
                # already converted to multi-primitive
                proper_new_primitives.append(p)

        #if old_prim == '':
        proper_new_prim_str = ''.join(proper_new_primitives)
        proper_new_prim_set = set(proper_new_primitives)
        old_prim_set = set(custom_list(old_prim))
        if old_prim_set != proper_new_prim_set:
            if new_prim != c and new_prim != '':

                ignore_ineq = False

                extra_in_new = proper_new_prim_set - old_prim_set
                extra_in_old = old_prim_set - proper_new_prim_set
                if extra_in_new == set('肉') and extra_in_old == set('月'):
                    ignore_ineq = True
                if extra_in_new == set('手') and extra_in_old == set('扌'):
                    ignore_ineq = True
                if extra_in_new == set('衣') and extra_in_old == set('衤'):
                    ignore_ineq = True
                if extra_in_new == set('已') and extra_in_old == set('己'):
                    ignore_ineq = True
                if extra_in_new == set('立口') and extra_in_old == set('咅'):
                    ignore_ineq = True
                if extra_in_new == set('疋') and extra_in_old == set(['[mending]']):
                    ignore_ineq = True
                if extra_in_new == set('吉') and extra_in_old == set(['[lidded_crock]']):
                    ignore_ineq = True
                if extra_in_new == set('戔') and extra_in_old == set('㦮'):
                    ignore_ineq = True
                if extra_in_new == set('僉') and extra_in_old == set('㑒'):
                    ignore_ineq = True
                if extra_in_new == set('襄') and extra_in_old == set('㐮'):
                    ignore_ineq = True

                if c == "砦":
                    print("sfdd")
                sec_prim_found = False
                if old_prim!='':
                    for extra_p in extra_in_new:
                        if extra_p not in kanji_keywords:
                            sec_prim_found = True
                        if extra_p in kanji_ids and kanji_ids[extra_p] > 2200:
                            sec_prim_found = True

                if not ignore_ineq:

                    if sec_prim_found:
                        if all_found:
                            change = [c,"sec_primitives",old_prim,proper_new_prim_str]#, str(id), str(freq)]
                        else:
                            change = [c,"sec_primitives",old_prim,proper_new_prim_str, 'Missing ' + ','.join(missing_new_primitives)]
                        #fw(change)
                    else:
                        if old_prim == '':
                            if all_found:
                                change = [c,"primitives",old_prim,proper_new_prim_str] #, str(id), str(freq)]
                            else:
                                change = [c,"primitives",old_prim,proper_new_prim_str, 'Missing ' + ','.join(missing_new_primitives)]
                            fw(change)



for p in unknown_primitives.keys():
    unknown_primitive_refs = unknown_primitives[p]
    if len(unknown_primitive_refs)>1:
        #print("%s\theisig_comment\t\tEditor\'s note: A non-Heisig primitive used by uncommon kanjis\t# %s" % (p, unknown_primitives[p]))
        fw([p, "heisig_comment","","Editor\'s note: A non-Heisig primitive used by uncommon kanjis", '# ' + unknown_primitives[p]])

f.close()

print("Total unknown primitives",len(unknown_primitives),"/ unknown occurrences",total_unknown_occurrences)