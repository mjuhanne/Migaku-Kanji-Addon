import sqlite3
from threading import RLock

import anki
import aqt
from .card_type import CardType
from . import config

from .util import addon_path, user_path, assure_user_dir, unique_characters, custom_list, list_to_primitive_str, get_proficiency_level_direction

ext_story_db_path = user_path("external_stories.db")

blacklist = ['head','arrow','spirit','world','not','bed','umbrella','twenty','key','village','box','ladle','mama','death','stamp','wing',
                'table','top hat','spring','scarecrow','saw','paragraph',
                'grass','face','guard','mask','spear','icicle','comb','rake',
                'nose','turtle','commander','plow','can','winter','zombie','poem','warehouse','call','charchoal']
whitelist = ['ball','forehead','alligator','self','belt',
                'line','floor','silver','float','samurai','monkey','seaweed']

wanikani_radical_conversion_table = {
    'spring' : 'bonsai',
    'leaf' : '[leaf]',
    'gun' : '𠂉',
    'stick' : '丨',
    'hat' : '𠆢',
    'triceratops' : '⺌',
    'beggar' : '[slingshot]',
    'horns': '丷',
    'spikes': '业',
    'viking' : '[schoolhouse]',
    'kick' : '[kick]',
    'cape' : 'ヿ',
    'cleat' : '爫',
    'pope' : '[pope]',
    'spring' : '𡗗',
    'squid' : '㑒',
    'yurt' : '[caverns]',
    'gladiator' : '[quarter]',
    'chinese' : '𦰩',
    'blackjack' : '龷',
    'trash'  : '𠫓',
    'bear' : '㠯',  
    'tofu' : '[rags]',
    'creeper' : '[creeper]',
    'bar' : '㦮',
    'grass' : '⺍',
    'zombie' : '[zombie]',
    'explosion' : '[sparkler]',
    'morning' : '𠦝',
    'death star' : '[butchers]',
    'comb' : '[staple_gun]',
    'hills' : '[hills]',
    'elf' : '[elf]',
    'coral' : '[coral]',
    'cactus' : '[cactus]',
    'satellite' : '[condor]',
    'psychopath' : '[psychopath]',

    'ト' : '卜',
    'ナ' : '𠂇',
    'メ' : '乂',
    'ｲ' : '亻',
    'ネ' : '礻',
    'ム' : '厶',
    '⻌' : '辶',
    }

def get_character_from_wanikani(c,m):
    if 'class="radical' in c:
        if m in wanikani_radical_conversion_table:
            c = wanikani_radical_conversion_table[m]
    else:
        if c in wanikani_radical_conversion_table:
            c = wanikani_radical_conversion_table[c]
    if c == '':
        c = m
    return c

class ExternalStoryDatabase:

    def __init__(self, parent):
        self.parent = parent
        self.initialize()

    # Open db
    def initialize(self):
        # check_same_thread set to false to allow gui thread updating while stuff is updated
        # only one thread ever accesses the db
        self.con = sqlite3.connect(ext_story_db_path, check_same_thread=False)
        self.lock = RLock()

        self.crs = self.con.cursor()
        self.crs.execute("PRAGMA case_sensitive_like=OFF")

        self.crs.execute(
            "CREATE TABLE IF NOT EXISTS stories ("
            "character TEXT NOT NULL,"
            "collection TEXT NOT NULL,"
            'keywords TEXT DEFAULT "",'
            'ckeywords TEXT DEFAULT "",'
            'story TEXT DEFAULT "",'
            'comment TEXT DEFAULT "",'
            'components TEXT DEFAULT "",'
            'PRIMARY KEY (character,collection)'
            ")"
        )

    def crs_execute(self, __sql: str, __parameters=()):
        self.lock.acquire(True)
        self.crs.execute(__sql, __parameters)
        self.lock.release()

    def crs_execute_and_commit(self, __sql: str, __parameters=()):
        self.lock.acquire(True)
        self.crs.execute(__sql, __parameters)
        self.con.commit()
        self.lock.release()

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

    def get_external_stories(self, character):

        stories = []
        r = self.crs_execute_and_fetch_all(
            f"SELECT collection,keywords,story,comment,components FROM stories WHERE character = (?)",
            (character,),
        )
        if r:
            for story in r:
                stories.append( { 
                    'Collection' : story[0],
                    'Keywords' : story[1],
                    'Story' : story[2],
                    'Comment' : story[3]
                })

        return stories

    def get_external_keywords(self, character):

        keywords = dict()
        conflicting_keywords = dict()
        r = self.crs_execute_and_fetch_all(
            f"SELECT collection,keywords,ckeywords FROM stories WHERE character = (?)",
            (character,),
        )
        if r:
            for story in r:
                keywords[story[0].lower()] = story[1].split(',') if story[1] != '' else []
                conflicting_keywords[story[0].lower()] = story[2].split(',') if story[2] != '' else []

        return keywords, conflicting_keywords

    def get_external_components(self, character):

        component_lists = dict()
        r = self.crs_execute_and_fetch_all(
            f"SELECT collection,components FROM stories WHERE character = (?)",
            (character,),
        )
        if r:
            for story in r:
                component_lists[story[0]] = custom_list(story[1])

        return component_lists


    def convert_external_stories(self, collection_name):


        self.crs_execute_and_commit("DELETE FROM stories WHERE collection=?", (collection_name,))

        if collection_name == "RRTK":
            deck_name = "RRTK Recognition Remembering The Kanji v2"
            note_name = "Heisig 書き方-28680"
            character_field = "Kanji"
            keyword_field = "Keyword"
            story_field = "My Story"
        elif collection_name == "WK":
            deck_name = "Wanikani Ultimate 3: Tokyo Drift"
            note_name = "Wanikani Ultimate 3"
            character_field = "Characters"
            components_field = "Components_Characters"
            components_meaning_field = "Components_Meaning"
            keyword_field = "Meaning"
            story_field = "Meaning_Mnemonic"
            comment_field = "Meaning_Hint"
            card_type_field = "Card_Type"
            reading_field = "Reading_Whitelist"
            reading_mnemonic_field = "Reading_Mnemonic"
            reading_hint_field = "Reading_Hint"

        else:
            raise Exception("Unknown collection!")

        characters_processed = []
        stories = []

        model = aqt.mw.col.models.by_name(note_name)
        if model is None:
            return []

        deck = aqt.mw.col.decks.by_name(deck_name)
        if deck is None:
            return []
        deck_id = deck["id"]


        nids = aqt.mw.col.db.all(
            f"SELECT c.nid FROM cards as c WHERE did={deck_id}"
        )

        for [nid] in nids:
            note = aqt.mw.col.get_note(nid)

            if note.mid != model["id"]:
                continue

            if collection_name == "RRTK":
                character = note[character_field]
                character = character.replace('<span style="color: rgb(66, 65, 61);">此</span>','此')
                keyword = note[keyword_field]
                keyword = keyword.replace('<b>','')
                keyword = keyword.replace('</b>','')
                keyword = keyword.replace('<br>','')
                keyword = keyword.replace('<strong>','')
                keyword = keyword.replace('</strong>','')
                keyword = keyword.replace('<span style="color: rgb(16, 8, 0);">But of course</span>','but of course')
                keyword = keyword.replace('therefore<font color="#100800">/ergo</font>','therefore/ergo')
                keyword = keyword.replace('&nbsp;',' ')
                comment = ''
                components = ''
                h_kw = self.parent.get_field(character,'heisig_keyword6')
                if h_kw != keyword:
                    print("Collection %s character %s keyword %s != heisig kw %s" % (collection_name,character,keyword,h_kw))
                keywords = keyword.replace('/',',')
                card_type = ''

            elif collection_name == "WK":

                card_type = note[card_type_field]
                if card_type == "Vocabulary":
                    continue

                keywords = note[keyword_field].lower()
                character = get_character_from_wanikani(note[character_field],keywords)

                if character in characters_processed:
                    continue

                comment = note[comment_field]
                component_list = [x.strip() for x in note[components_field].split(',')]
                components_meanings = [x.strip().lower() for x in note[components_meaning_field].split(',')]
                final_components = []
                for (c,m) in zip(component_list,components_meanings):
                    c = get_character_from_wanikani(c,m)
                    final_components.append(c)
                components = ''.join(final_components)

                characters_processed.append(character)

                # add separate entry for Wanikani reading
                reading_mnemonic = note[reading_field] + ': ' + note[reading_mnemonic_field]
                stories.append( (character,'WR','','',reading_mnemonic,note[reading_hint_field],''))


            heisig_kw_list = []
            if not self.parent.does_character_exist(character):
                print("Warning! Character %s in collection %s does not exist!" % (character,collection_name))
            else:
                heisig_keyword = self.parent.get_field(character,"heisig_keyword6")
                if heisig_keyword != '':
                    heisig_kw_list.append(heisig_keyword)
                pkw_list = self.parent.get_field(character,"primitive_keywords")
                heisig_kw_list += pkw_list

                if len(heisig_kw_list) == 0:
                    print("Warning! Character %s in collection %s does not have heisig keyword!" % (character,collection_name))


            keyword_list = [x.strip() for x in keywords.split(',')]
            conflicting_keywords = []
            for kw in keyword_list:
                if kw not in heisig_kw_list:
                    for c,kws in self.parent.search_engine.keyword_cache.items():
                        if c != character:
                            kw_list = [x.strip() for x in kws.split(',')]
                            for other_kw in kw_list:
                                if kw == other_kw:
                                    conflict = False
                                    if card_type != "Radical":
                                        if kw not in whitelist:
                                            conflict=True
                                    else:
                                        if kw in blacklist:
                                            conflict=True
                                        else:
                                            print("Warning! %s %s in collection %s with conflicting keyword '%s' with character %s (%s) added anyway.." 
                                                % (card_type,character,collection_name, kw, c, kws))
                                    
                                    if conflict:
                                        #print("Warning! %s %s in collection %s has conflicting keyword '%s' with character %s (%s)!" 
                                        #    % (card_type,character,collection_name, kw, c, kws))
                                        if kw not in conflicting_keywords:
                                            conflicting_keywords.append(kw)

            stories.append( (character,collection_name,','.join(keyword_list),','.join(conflicting_keywords),note[story_field],comment,components))

        self.crs_executemany_and_commit(
            f"INSERT OR REPLACE INTO stories (character, collection, keywords, ckeywords, story, comment, components) values (?,?,?,?,?,?,?)",
            stories,
        )


