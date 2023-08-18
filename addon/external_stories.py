import sqlite3
from threading import RLock

import anki
import aqt
from .card_type import CardType
from . import config

from .util import addon_path, user_path, assure_user_dir, unique_characters, custom_list, list_to_primitive_str, get_proficiency_level_direction

ext_story_db_path = user_path("external_stories.db")

class ExternalStoryDatabase:

    def __init__(self):
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
            "character TEXT NOT NULL PRIMARY KEY,"
            "collection TEXT,"
            'keyword TEXT DEFAULT "",'
            'story TEXT DEFAULT ""'
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
            f"SELECT collection,keyword,story FROM stories WHERE character = (?)",
            (character,),
        )
        if r:
            stories = []
            for story in r:
                stories.append( { 
                    'Collection' : story[0],
                    'Keyword' : story[1],
                    'Story' : story[2]
                })

        return stories



    def convert_external_stories(self, collection_name):


        self.crs_execute_and_commit("DELETE FROM stories WHERE collection=?", (collection_name,))

        """
                for e in config.get("card_type_learn_ahead", {}).get(ct.label, []):
                    deck_name = e["deck"]
        """
        deck_name = "RRTK Recognition Remembering The Kanji v2"
        note_name = "Heisig 書き方-28680"
        character_field = "Kanji"
        keyword_field = "Keyword"
        story_field = "My Story"

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

            stories.append( (note[character_field],note[keyword_field],note[story_field] ))

        self.crs_executemany_and_commit(
            f"INSERT OR REPLACE INTO stories (character, keyword, story) values (?,?,?)",
            stories,
        )

