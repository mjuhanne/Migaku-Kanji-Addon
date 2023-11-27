import os
import json
import base64
import sqlite3
from collections import defaultdict, OrderedDict
from threading import RLock

import anki
import aqt

from .util import addon_path, user_path, assure_user_dir, unique_characters, custom_list, get_proficiency_level_direction, list_to_primitive_str
from .errors import InvalidStateError, InvalidDeckError
from .card_type import CardType
from . import config
from . import text_parser
from .kanji_confirm_dialog import KanjiConfirmDialog
from .search_engine import SearchEngine
#from .stories_converter import StoriesConverter
from .story_db import StoryDatabase

from aqt.operations import CollectionOp, OpChanges

def add_notes_blocking(col, notes, deck_id, checkpoint):
    from . import add_note_no_hook

    print("**** Adding %d notes to checkpoint %s" % (len(notes), checkpoint))
    pos = col.add_custom_undo_entry(checkpoint)

    for note in notes:
        add_note_no_hook(col, note, deck_id)

    return col.merge_undo_entries(pos)

def add_notes_op(*, notes, deck_id, checkpoint) -> CollectionOp[OpChanges]:
    return CollectionOp(aqt.mw, 
        lambda col, notes=notes,deck_id=deck_id,checkpoint=checkpoint: 
            add_notes_blocking(col, notes, deck_id, checkpoint)
    )


def add_notes(notes, deck_id, checkpoint, success_func):

    if checkpoint is None:
        checkpoint = 'dummy_checkpoint'

    # Current Anki undo queue has maximum length of 30 changes and
    # will break if attempt is made to merge more changes into single checkpoint.
    # For this reason we have to create additional checkpoints for every 30 notes added
    maximum_notes_per_checkpoint = 29
    notes_per_checkpoint = [ notes[i:i + maximum_notes_per_checkpoint] 
        for i in range(0, len(notes), maximum_notes_per_checkpoint)
    ]

    checkpoint_number = 0
    for notes_in_checkpoint in notes_per_checkpoint:
        checkpoint_name = checkpoint + '_' + str(checkpoint_number+1)
        print("Creating checkpoint %s" % checkpoint_name)

        op = add_notes_op(notes=notes_in_checkpoint, deck_id=deck_id, checkpoint=checkpoint_name )
        if checkpoint_number == len(notes_per_checkpoint)-1:
            # run success_func only after last batch (checkpoint) is processed
            op.success(success_func)
        op.run_in_background()
        checkpoint_number += 1


kanji_db_path = addon_path("kanji.db")
user_db_path = user_path("user.db")


def clean_character_field(f):
    f = f.lstrip()
    f = text_parser.html_regex.sub("", f)
    if len(f):
        # Leave [primitive_tag] as it is, otherwise return the single unicode character
        if f[0] == '[':
            return f
        return f[0]
    return ""

class KanjiDB:
    def __init__(self):
        self.initialize()

    # Open db
    def initialize(self):
        # check_same_thread set to false to allow gui thread updating while stuff is updated
        # only one thread ever accesses the db
        self.con = sqlite3.connect(kanji_db_path, check_same_thread=False)
        self.lock = RLock()

        self.crs = self.con.cursor()
        self.crs.execute("PRAGMA case_sensitive_like=OFF")

        assure_user_dir()
        self.crs.execute(f'ATTACH DATABASE "{user_db_path}" AS usr;')

        for ct in CardType:
            # Negative card id -> manually marked as known
            self.crs.execute(
                f"CREATE TABLE IF NOT EXISTS usr.{ct.label}_card_ids("
                "character TEXT NOT NULL PRIMARY KEY,"
                "card_id INTEGER NOT NULL"
                ")"
            )

        self.crs.execute(
            "CREATE TABLE IF NOT EXISTS usr.words("
            "note_id INTEGER NOT NULL,"
            "word TEXT NOT NULL,"
            'reading TEXT DEFAULT "",'
            "is_new INTEGER DEFAULT 0"
            ")"
        )

        self.crs.execute(
            "CREATE TABLE IF NOT EXISTS usr.keywords("
            "character TEXT NOT NULL PRIMARY KEY,"
            'usr_keyword TEXT DEFAULT "",'
            'usr_primitive_keyword TEXT DEFAULT ""'
            ")"
        )

        self.crs.execute(
            "CREATE TABLE IF NOT EXISTS usr.stories("
            "character TEXT NOT NULL PRIMARY KEY,"
            "usr_story TEXT NOT NULL"
            ")"
        )

        try:
            self.crs.execute(
                "ALTER TABLE usr.words ADD COLUMN is_new INTEGER DEFAULT 0"
            )
            self.con.commit()
        except sqlite3.OperationalError:
            pass

        try:
            self.crs.execute(
                'ALTER TABLE usr.keywords ADD COLUMN usr_primitive_keyword TEXT DEFAULT ""'
            )
            self.con.commit()
        except sqlite3.OperationalError:
            pass

        self.story_db = StoryDatabase(self)
        #self.stories_converter = StoriesConverter(self)
        self.search_engine = SearchEngine(self)

    # Close db
    def shutdown(self):
        self.crs.close()
        self.con.close()

    def crs_execute(self, __sql: str, __parameters=()):
        with self.lock:
            self.crs.execute(__sql, __parameters)

    def crs_execute_and_commit(self, __sql: str, __parameters=()):
        with self.lock:
            self.crs.execute(__sql, __parameters)
            self.con.commit()

    def crs_executemany_and_commit(self, __sql: str, __seq_of_parameters):
        with self.lock:
            self.crs.executemany(__sql, __seq_of_parameters)
            self.con.commit()

    def crs_execute_and_fetch_one(self, __sql: str, __parameters=()):
        with self.lock:
            self.crs.execute(__sql, __parameters)
            r = self.crs.fetchone()
        return r

    def crs_execute_and_fetch_all(self, __sql: str, __parameters=()):
        with self.lock:
            self.crs.execute(__sql, __parameters)
            r = self.crs.fetchall()
        return r

    def reset(self):
        for ct in CardType:
            self.crs_execute(f"DELETE FROM usr.{ct.label}_card_ids")
        self.crs_execute("DELETE FROM usr.words")
        self.crs_execute("DELETE FROM usr.keywords")
        self.crs_execute("DELETE FROM usr.stories")

    def reset_marked_known(self, card_type):
        self.crs_execute(f"DELETE FROM usr.{card_type.label}_card_ids WHERE card_id=-1")

    def reset_custom_keywods(self):
        self.crs_execute("DELETE FROM usr.keywords")

    def reset_custom_stories(self):
        self.crs_execute("DELETE FROM usr.stories")

    # Recursivly finds new characters given a specific character
    def _new_characters_find(self, card_type, character, out, max_characters=-1):
        # Check if max characters already reached
        if max_characters >= 0 and len(out) >= max_characters:
            return

        # Check if character was already handled
        if character in out:
            return

        primitives = self.story_db.get_primitives(character,card_type)

        # Recusivly add primitives that need to be learned if enabled
        if card_type.add_primitives:
            for p in primitives:
                if p == character:
                    continue
                self._new_characters_find(card_type, p, out, max_characters)

        # Check if max characters already reached
        if max_characters >= 0 and len(out) >= max_characters:
            return

        # Check if card already exists for character
        table = f"usr.{card_type.label}_card_ids"
        r = self.crs_execute_and_fetch_one(
            f"SELECT COUNT(*) FROM {table} "
            "WHERE character == (?) AND card_id NOT NULL",
            (character,),
        )

        if r[0] != 0:
            return

        out.append(character)

    # Recursivley find new characters to learn
    def new_characters(self, card_type, input_data, max_characters=-1):
        if type(input_data) == str:
            input_data = set(input_data)

        ret = []
        for c in input_data:
            self._new_characters_find(card_type, c, ret, max_characters)
        return ret

    def find_next_characters(
        self,
        card_type,
        max_characters,
        column="frequency_rank",
        order="ASC",
        condition=None,
    ):
        table = f"usr.{card_type.label}_card_ids"

        if condition is None:
            condition = ""
        else:
            condition = f"AND {column} {condition} "

        r = self.crs_execute_and_fetch_all(
            "SELECT characters.character FROM characters "
            f"LEFT OUTER JOIN {table} ON characters.character == {table}.character "
            f"WHERE {table}.card_id IS NULL "
            f"{condition}"
            f"ORDER BY {column} {order} "
            "LIMIT (?)",
            (max_characters,),
        )
        candidates = [x[0] for x in r]

        return self.new_characters(card_type, candidates, max_characters)

    # Recalc all kanji cards created
    def recalc_user_cards(self, card_type):
        print("Recalc user cards: %s" % card_type.label)
        table = f"usr.{card_type.label}_card_ids"

        self.crs_execute(
            f"DELETE FROM {table} WHERE card_id >= 0"
        )  # don't nuke words manually marked known!

        character_card_ids = {}

        recognized_types = (
            config.get("card_type_recognized", {}).get(card_type.label, []).copy()
        )

        recognized_types.append(
            {
                "deck": card_type.deck_name,
                "note": card_type.model_name,
                "card": 0,
                "field": "Character",
            }
        )

        for entry in recognized_types:
            entry_note = entry["note"]
            entry_card = entry["card"]
            entry_deck = entry["deck"]
            entry_field = entry["field"]

            find_filter = [f'"note:{entry_note}"', f'"card:{entry_card+1}"']
            if entry_deck != "All":
                find_filter.append(f'"deck:{entry_deck}"')

            card_ids = aqt.mw.col.find_cards(" AND ".join(find_filter))

            for card_id in card_ids:
                card = aqt.mw.col.get_card(card_id)
                note = card.note()
                character = clean_character_field(note[entry_field])
                character_card_ids[character] = card_id

        self.crs_executemany_and_commit(
            f"INSERT OR REPLACE INTO {table} (character, card_id) values (?,?)",
            character_card_ids.items(),
        )

    # Recalc user all works associated with kanji from notes
    def recalc_user_words(self):
        if not text_parser.is_available():
            return

        recognized_types = config.get("word_recognized", [])

        note_id_words = set()

        note_ids_not_new = set()

        for check_new in [False, True]:
            for entry in recognized_types:
                entry_note = entry["note"]
                entry_card = entry["card"]
                entry_deck = entry["deck"]
                entry_field = entry["field"]

                find_filter = [f'"note:{entry_note}"', f'"card:{entry_card+1}"']
                if entry_deck != "All":
                    find_filter.append(f'"deck:{entry_deck}"')
                if check_new:
                    find_filter.append("(is:new AND -is:suspended)")
                else:
                    find_filter.append("(is:learn OR is:review)")

                entry_note_ids = aqt.mw.col.find_notes(" AND ".join(find_filter))

                for note_id in entry_note_ids:
                    if not check_new:
                        note_ids_not_new.add(note_id)

                    note = aqt.mw.col.get_note(note_id)
                    field_value = note[entry_field]
                    words = text_parser.get_cjk_words(field_value, reading=True)

                    for word in words:
                        note_id_words.add((note_id, *word))

        self.crs_execute("DELETE FROM usr.words")

        insert_note_id_words = set()
        for note_id, word, reading in note_id_words:
            is_new = note_id not in note_ids_not_new
            insert_note_id_words.add((note_id, word, reading, is_new))

        # Insert new mapping
        self.crs_executemany_and_commit(
            "INSERT INTO usr.words (note_id,word,reading,is_new) VALUES (?,?,?,?)",
            insert_note_id_words,
        )

    def on_note_update(self, note_id, deck_id, is_new=False):
        try:
            note = aqt.mw.col.get_note(note_id)
        except Exception:
            # TODO: properly check if this is related to card import/export instead of this mess.
            return

        # Could allow more features if Migaku JA isn't installed but too lazy rn
        if not text_parser.is_available():
            return

        # Remove existing word entries for note
        self.crs_execute_and_commit("DELETE FROM usr.words WHERE note_id = (?)", (note_id,))

        # Add words from note
        words = set()

        for wr in config.get("word_recognized", []):
            wr_note = wr["note"]
            wr_deck_name = wr["deck"]
            wr_field = wr["field"]

            wr_model = aqt.mw.col.models.by_name(wr_note)
            if wr_model is None:
                continue
            if note.mid != wr_model["id"]:
                continue

            if wr_deck_name != "All":
                wr_deck = aqt.mw.col.decks.by_name(wr_deck_name)
                if wr_deck is None:
                    continue
                if deck_id != wr_deck["id"]:
                    continue

            field_value = note[wr_field]
            words.update(text_parser.get_cjk_words(field_value, reading=True))

        self.crs_executemany_and_commit(
            "INSERT INTO usr.words (note_id,word,reading,is_new) VALUES (?,?,?,?)",
            [(note_id, w, r, is_new) for (w, r) in words],
        )

        # Get unique kanji
        kanji = set()

        for wr in words:
            kanji.update(text_parser.filter_cjk(wr[0]))

        # Update kanji notes
        for ct in CardType:
            if not ct.auto_card_refresh:
                continue

            mid = ct.model_id()
            for k in kanji:
                r = self.crs_execute_and_fetch_one(
                    f"SELECT card_id FROM usr.{ct.label}_card_ids WHERE character = (?)",
                    (k,),
                )
                if r:
                    cid = r[0]
                    try:
                        card = aqt.mw.col.get_card(cid)
                    except Exception:  # anki.errors.NotFoundError for newer versions
                        continue
                    if card:
                        note = card.note()
                        if note:
                            if note.mid == mid:
                                self.refresh_note(note, do_flush=True)

        # Create new cards
        if is_new:
            new_kanji_for_msg = OrderedDict()

            for ct in CardType:
                if not ct.auto_card_creation:
                    continue

                self.recalc_user_cards(ct)
                new_chars = self.new_characters(ct, kanji)

                if len(new_chars) > 0:
                    if ct.auto_card_creation_msg:
                        new_kanji_for_msg[ct] = new_chars
                    else:
                        self.make_cards_from_characters(
                            ct, new_chars, "Automatic Kanji Card Cration"
                        )

            if len(new_kanji_for_msg) > 0:
                KanjiConfirmDialog.show_new_kanji(new_kanji_for_msg, aqt.mw)

    def refresh_learn_ahead(self, show_confirm_dialog=False):
        new_kanji_for_msg = OrderedDict()

        for ct in CardType:
            for e in config.get("card_type_learn_ahead", {}).get(ct.label, []):
                deck_name = e["deck"]
                max_num = e["num"]

                deck = aqt.mw.col.decks.by_name(deck_name)
                if deck is None:
                    continue
                deck_id = deck["id"]

                new = self.new_learn_ahead_kanji(ct, deck_id, max_num)
                print("***** Card type %s Deck: %s - New from unstudied: %s *****" % (ct.label,deck_name,new))

                if len(new) > 0:
                    if not show_confirm_dialog:
                        try:
                            self.make_cards_from_characters(ct, new, None)
                        except InvalidStateError:
                            # Ignore this silently...
                            pass
                    else:
                        new_kanji_for_msg[ct] = new

        if len(new_kanji_for_msg) > 0:
            KanjiConfirmDialog.show_new_kanji(new_kanji_for_msg, aqt.mw)


    def scan_for_missing_kanji(self, callback=None):

        missing_characters_per_card_type = OrderedDict()
        for ct in CardType:
            missing_characters = []
            for e in config.get("card_type_learn_ahead", {}).get(ct.label, []):
                deck_name = e["deck"]
                max_num = e["num"]

                deck = aqt.mw.col.decks.by_name(deck_name)
                if deck is None:
                    continue
                deck_id = deck["id"]

                missing_characters_for_this_deck = self.new_learn_ahead_kanji(ct, deck_id, -1, 2, callback=callback)
                for c in missing_characters_for_this_deck:
                    if c not in missing_characters:
                        missing_characters.append(c)

            if len(missing_characters) > 0:
                missing_characters_per_card_type[ct] = missing_characters

        if len(missing_characters_per_card_type) > 0:
            KanjiConfirmDialog.show_new_kanji(missing_characters_per_card_type, aqt.mw)


    # checks learn ahead for a given deck
    # status_type:  
    #   0: New card. Applies to suspended or non-suspended cards
    #   1: Learning, but due date not yet assigned (?)
    #   2: Normal learning.
    def new_learn_ahead_kanji(self, card_type, deck_id, max_cards, status_type=0, callback=None):
        if max_cards >= 0:
            nids = aqt.mw.col.db.all(
                f"SELECT c.nid FROM cards as c WHERE did={deck_id} AND type={status_type} ORDER BY c.due AND queue>=0 LIMIT {max_cards}"
            )
        else:
            # this will scan entire deck for missing kanji (actually only max 1000 cards with nearest due date)
            nids = aqt.mw.col.db.all(
                f"SELECT c.nid FROM cards as c WHERE did={deck_id} AND type={status_type} ORDER BY c.due AND queue>=0"
            )

        kanji_seen = set()
        kanji = []  # to preserve order

        num_notes = len(nids)
            
        for i, [nid] in enumerate(nids):
            note = aqt.mw.col.get_note(nid)

            for wr in config.get("word_recognized", []):
                wr_note = wr["note"]
                wr_deck_name = wr["deck"]
                wr_field = wr["field"]

                wr_model = aqt.mw.col.models.by_name(wr_note)
                if wr_model is None:
                    continue
                if note.mid != wr_model["id"]:
                    continue

                if wr_deck_name != "All":
                    wr_deck = aqt.mw.col.decks.by_name(wr_deck_name)
                    if wr_deck is None:
                        continue
                    if deck_id != wr_deck["id"]:
                        continue
                    
                if callback and ((i + 1) % 25) == 0:
                    callback(f"Scanning note ({i+1}/{num_notes}) in deck '{wr_deck_name}' ({card_type.label})")
                        
                field_value = note[wr_field]
                for k in text_parser.filter_cjk(field_value):
                    if k not in kanji_seen:
                        kanji.append(k)

        return aqt.mw.migaku_kanji_db.new_characters(card_type, kanji)

    def get_field(self, character, field_name):
        r = self.crs_execute_and_fetch_one(
            f"SELECT {field_name} FROM characters WHERE character=?",
            (character,),
        )
        if r:
            return r[0]
        return None

    # Returns a list of tuples: (word, reading, note id list, is_new)
    # Seen ones first, then sorted by amount of note ids.
    def get_character_words(self, character):
        character_wildcard = f"%{character}%"
        r = self.crs_execute_and_fetch_all(
            "SELECT note_id, word, reading, is_new FROM usr.words WHERE word LIKE (?)",
            (character_wildcard,),
        )

        words_dict = defaultdict(list)
        words_not_new = set()

        for note_id, word, reading, is_new in r:
            words_dict[(word, reading)].append(note_id)
            if not is_new:
                words_not_new.add((word, reading))

        word_list = []
        for (word, reading), note_ids in words_dict.items():
            is_new = (word, reading) not in words_not_new
            word_list.append((word, reading, note_ids, is_new))

        word_list.sort(key=lambda entry: (not entry[3], len(entry[2])), reverse=True)

        return word_list

    def set_character_usr_keyowrd(self, character, keyword, primitive_keyword):
        self.crs_execute_and_commit(
            "INSERT OR REPLACE INTO usr.keywords (character,usr_keyword,usr_primitive_keyword) VALUES (?,?,?)",
            (character, keyword, primitive_keyword),
        )

        self.refresh_notes_for_character(character)

    def get_character_usr_keyowrd(self, character):
        r = self.crs_execute_and_fetch_one(
            "SELECT usr_keyword, usr_primitive_keyword FROM usr.keywords WHERE character=?",
            (character,),
        )
        if r:
            return (r[0], r[1])
        else:
            return ("", "")

    # TODO: Also allow setting primitive keywords
    def mass_set_character_usr_keyowrd(self, character_keywords):
        self.crs_executemany_and_commit(
            "INSERT OR REPLACE INTO usr.keywords (character,usr_keyword) VALUES (?,?)",
            character_keywords.items(),
        )

    def set_character_usr_story(self, character, story):
        self.crs_execute_and_commit(
            "INSERT OR REPLACE INTO usr.stories (character,usr_story) VALUES (?,?)",
            (character, story),
        )

        self.refresh_notes_for_character(character)

    def get_character_usr_story(self, character):
        r = self.crs_execute_and_fetch_one(
            f"SELECT usr_story FROM usr.stories WHERE character=?",
            (character,),
        )
        if r:
            return r[0]
        else:
            return ""


    def does_character_exist(self, character):
        r = self.crs_execute_and_fetch_one(
            "SELECT character FROM characters WHERE character=?",
            (character,),
        )
        if r:
            return True
        return False

        
    def mass_set_character_usr_story(self, character_stories):
        self.crs_executemany_and_commit(
            "INSERT OR REPLACE INTO usr.stories (character,usr_story) VALUES (?,?)",
            character_stories.items(),
        )

    def set_character_known(self, card_type, character, known=True):
        if known == True:
            self.crs_execute_and_commit(
                f"INSERT OR REPLACE INTO usr.{card_type.label}_card_ids (character,card_id) VALUES (?,?)",
                (character, -1),
            )
        else:
            self.crs_execute_and_commit(
                f"DELETE FROM usr.{card_type.label}_card_ids WHERE character == ?",
                (character,),
            )

    def mass_set_characters_known(self, card_type, characters):
        self.crs_executemany_and_commit(
            f"INSERT OR IGNORE INTO usr.{card_type.label}_card_ids (character,card_id) VALUES (?,?)",
            [(c, -1) for c in characters],
        )

    def refresh_notes_for_character(self, character):
        ct_find_filter = [f'"note:{ct.model_name}" AND "Character:{character}"' for ct in CardType]
        note_ids = aqt.mw.col.find_notes(
            " OR ".join(ct_find_filter) 
        )

        for note_id in note_ids:
            note = aqt.mw.col.get_note(note_id)
            self.refresh_note(note, do_flush=True)

    def make_card_unsafe(self, card_type, character):
        from . import add_note_no_hook

        deck_name = card_type.deck_name
        model_name = card_type.model_name

        deck = aqt.mw.col.decks.by_name(deck_name)
        if deck is None:
            raise InvalidDeckError(card_type)
        deck_id = deck["id"]

        model = aqt.mw.col.models.by_name(model_name)

        note = anki.notes.Note(aqt.mw.col, model)
        note["Character"] = character
        self.refresh_note(note)
        add_note_no_hook(aqt.mw.col, note, deck_id)

        return note

        
    def make_cards_from_characters(self, card_type, new_characters, checkpoint=None):

        # Just to be sure...
        self.recalc_user_cards(card_type)

        characters = self.new_characters(card_type, new_characters)

        deck_name = card_type.deck_name
        model_name = card_type.model_name

        deck = aqt.mw.col.decks.by_name(deck_name)
        if deck is None:
            raise InvalidDeckError(card_type)

        deck_id = deck["id"]
        model = aqt.mw.col.models.by_name(model_name)

        new_notes = []

        for c in characters:
            note = anki.notes.Note(aqt.mw.col, model)
            note["Character"] = c
            self.refresh_note(note)
            new_notes.append(note)

        add_notes(new_notes, deck_id, checkpoint,lambda result : self.recalc_user_cards(card_type) )

    def refresh_note(self, note, do_flush=False):
        c = clean_character_field(note["Character"])
        if len(c) < 1:
            return
        note["Character"] = c

        # get the card type for this note
        model_name = note.note_type()['name']
        card_type = None
        for ct in CardType:
            if ct.model_name == model_name:
                card_type = ct

        r = self.get_kanji_result_data(c, card_type=card_type, card_ids=False)
        data_json = json.dumps(r, ensure_ascii=True)
        data_json_b64_b = base64.b64encode(data_json.encode("utf-8"))
        data_json_b64 = str(data_json_b64_b, "utf-8")
        note["MigakuData"] = data_json_b64

        if c[0] == '[':
            svg_name = c[1:-1] + ".svg"
        else:
            svg_name = "%05x.svg" % ord(c)

        # Try to find the KanjiVG file first in supplementary directory and
        # only then from the main repository
        svg_path = addon_path("kanjivg-supplementary", svg_name)
        if not os.path.exists(svg_path):
            svg_path = addon_path("kanjivg", svg_name)
            if not os.path.exists(svg_path):
                svg_path = ''

        if svg_path != '':
            with open(svg_path, "r", encoding="utf-8") as file:
                svg_data = file.read()

            note["StrokeOrder"] = svg_data
        else:
            note["StrokeOrder"] = ""

        if do_flush:
            note.flush()

    # If the deck has cards that have now references for new primitives 
    # which are not yet included in the stack, add them.
    def scan_for_missing_primitives(self):
        new_kanji_for_msg = OrderedDict()

        for ct in CardType:
            if not ct.add_primitives:
                continue

            find_filter = f'"deck:{ct.deck_name}"'
            note_ids = aqt.mw.col.find_notes(find_filter)

            all_characters_in_the_deck = []
            for i, note_id in enumerate(note_ids):
                note = aqt.mw.col.get_note(note_id)
                c = clean_character_field(note["Character"])
                all_characters_in_the_deck.append(c)

            new_characters = self.new_characters(ct, all_characters_in_the_deck, -1)
            if len(new_characters) > 0:
                new_kanji_for_msg[ct] = new_characters

        if len(new_kanji_for_msg) > 0:
            KanjiConfirmDialog.show_new_kanji(new_kanji_for_msg, aqt.mw)

    # Recalc everything
    def recalc_all(self, callback=None):
        if callback:
            callback("Scanning kanji cards...")

        for ct in CardType:
            self.recalc_user_cards(ct)

        if callback:
            callback("Refreshing collection words...")

        self.recalc_user_words()

        self.scan_for_missing_primitives()

        find_filter = [f'"note:{ct.model_name}"' for ct in CardType]
        note_ids = aqt.mw.col.find_notes(" OR ".join(find_filter))
        num_notes = len(note_ids)

        for i, note_id in enumerate(note_ids):
            note = aqt.mw.col.get_note(note_id)
            self.refresh_note(note, do_flush=True)

            if callback and ((i + 1) % 25) == 0:
                callback(f"Refreshing kanji cards... ({i+1}/{num_notes})")

    def is_included_in_proficiency_level(self, character, proficiency_type, proficiency_level):
        value = self.get_field(character, proficiency_type)
        direction = get_proficiency_level_direction(proficiency_type)
        if value is not None:
            if value == '':
                return False
            if direction == "ASC":
                if value <= proficiency_level:
                    return True
            else:
                if value >= proficiency_level:
                    return True
        return False

    # The primitive is defined rare if it's not included in target proficiency level 
    # curriculum and if it is referenced by less than 'minimum_primitive_occurrence' 
    # references from kanjis that match the target level
    # (e.g. Kanken level 2 or more common)
    def is_primitive_rare(self, character, card_type):
                
        proficiency_fields = card_type.target_proficiency_level.split('_')
        proficiency_type = proficiency_fields[0]
        proficiency_level = float(proficiency_fields[1])

        if self.is_included_in_proficiency_level(character, proficiency_type, proficiency_level):
            return False
        count = 0
    
        primitive_of = self.story_db.get_primitive_of(character)
        for p in primitive_of:
            if self.is_included_in_proficiency_level(p, proficiency_type, proficiency_level):
                count += 1
        return count < card_type.minimum_primitive_occurrence
            
    def get_kanji_result_data(
        self,
        character,
        card_ids=True,
        detail_primitives=True,
        detail_primitive_of=True,
        words=True,
        user_data=False,
        card_type=None,
    ):
        ret = {
            "character": character,
            "has_result": False,
        }

        # (field_name, load_function, column)
        _ = lambda x: x
        requested_fields = [
            ("stroke_count", _, None),
            ("onyomi", json.loads, None),
            ("kunyomi", json.loads, None),
            ("nanori", json.loads, None),
            ("meanings", json.loads, None),
            ("frequency_rank", _, None),
            ("grade", _, None),
            ("jlpt", _, None),
            ("kanken", _, None),
            ("radicals", list, None),
            ("words_default", json.loads, None),
            ("usr_keyword", _, "usr.keywords.usr_keyword"),
            ("usr_primitive_keyword", _, "usr.keywords.usr_primitive_keyword"),
            ("usr_story", _, "usr.stories.usr_story"),
        ]

        if card_ids:
            for ct in CardType:
                requested_fields.append(
                    (f"{ct.label}_card_id", _, f"usr.{ct.label}_card_ids.card_id")
                )

        fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

        joins = [
            f"LEFT OUTER JOIN usr.keywords ON characters.character == usr.keywords.character ",
            f"LEFT OUTER JOIN usr.stories ON characters.character == usr.stories.character ",
            f"LEFT OUTER JOIN usr.modified_values ON characters.character == usr.modified_values.character "
        ]
        if card_ids:
            joins.extend(
                f"LEFT OUTER JOIN usr.{ct.label}_card_ids ON characters.character == usr.{ct.label}_card_ids.character "
                for ct in CardType
            )
        joins_txt = "".join(joins)

        raw_data = self.crs_execute_and_fetch_one(
            f"SELECT {fields} FROM characters {joins_txt} "
            "WHERE characters.character = (?)",
            (character,),
        )

        if raw_data:
            ret["has_result"] = True

            for data, (name, load_func, _) in zip(raw_data, requested_fields):
                ret[name] = load_func(data)

            if words:
                ret["words"] = self.get_character_words(character)
            
            stories = self.story_db.get_stories(character)
            
            ret["primitive_of"] = self.story_db.get_primitive_of(character)
            ret["stories"] = stories
            ret["main_keyword"] = self.story_db.extract_main_keyword(stories)
            
            ret["primitives"] = stories["h"]["primitives"] if 'h' in stories else []
            ret["primitive_alternatives"] = stories["h"]["primitive_alternatives"] if 'h' in stories else []

            ret["heisig_id5"] = None
            ret["heisig_id6"] = None
            if 'h' in stories:
                ids = stories["h"]["id"]
                if ids is not None:
                    ids = ids.split(',')
                    if len(ids)>0 and ids[0] != '':
                        ret["heisig_id5"] = int(ids[0])
                    if len(ids)>1 and ids[1] != '':
                        ret["heisig_id6"] = int(ids[1])

                if '' in stories["h"]["keywords"]:
                    stories["h"]["keywords"].remove("")
                
            ret["wk"] = None
            if 'wk' in stories:
                if stories["wk"]["id"] is not None:
                    ret["wk"] = int(stories["wk"]["id"])

            ret["is_rare"] = self.is_primitive_rare(character, card_type)

            ret["primitives_detail"] = {}
            if detail_primitives:

                for source in stories.keys():

                    primitives = stories[source]["primitives"]
                    primitives_detail = []

                    for p in primitives:
                        primitives_detail.append(
                            self.get_kanji_result_data(
                                p,
                                card_ids=False,
                                detail_primitives=False,
                                detail_primitive_of=False,
                                words=False,
                                card_type=card_type,
                            )
                        )

                    ret["primitives_detail"][source.lower()] = primitives_detail

            if detail_primitive_of:
                primitive_of_detail = []

                for pc in ret["primitive_of"]:
                    primitive_of_detail.append(
                        self.get_kanji_result_data(
                            pc,
                            card_ids=False,
                            detail_primitives=False,
                            detail_primitive_of=False,
                            words=False,
                            card_type=card_type,
                        )
                    )

                ret["primitive_of_detail"] = primitive_of_detail

            if user_data:
                ret["user_data"] = {}
                for ct in CardType:
                    ct_card_id = ret[f"{ct.label}_card_id"]
                    ct_user_data = ""
                    if ct_card_id:
                        try:
                            ct_card = aqt.mw.col.get_card(ct_card_id)
                            ct_user_data = ct_card.note()["UserData"]
                        except:
                            pass
                    ret["user_data"][ct.label] = ct_user_data

        return ret
