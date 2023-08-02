import json
from .util import custom_list

def j2c(d):
    if d is not None:
        item = json.loads(d)
        return ", ".join(item)
    else:
        return ""

def csv_to_list(csv):
    value_list = csv.split(',')
    return [value.strip() for value in value_list]

# we ignore these radicals for now because they don't have a keyword containing 
# kanji counterpart in our database
ignore_radicals = ['亅','屮','禸','爻','尢','无','彑','黽','鬲','鬥','齊','龠','黹','黹','鬯']

# this table links radicals to their Heisig primitive counterpart to allow for
# even better search capability
# (some of them have identical visual look but differ only in Unicode)
unicode_conversion_table = {
    'ノ' : '丿',
    '｜' : '丨',
    '⺅' : '亻',
    '⺾' : '艹',
    '⺹' : '老',
    '爿' : '丬',
    '辶' : '辶',
}

def convert_to_correct_unicode_character(c):
    if c in unicode_conversion_table:
        return unicode_conversion_table[c]
    return c

class SearchEngine:

    def __init__(self, db_cursor):
        self.crs = db_cursor
        self.create_cache()

    def recursively_find_all_primitives(self, character):
        if character not in self.primitive_set_cache:
            return set()
        primitives = self.primitive_set_cache[character] or set
        if len(primitives) == 1 and character in primitives:
            # skip all the primitives that have only themselves listed as primitives
            return set()
        found_primitives = set(primitives)
        # recursively find all primitives
        for p in primitives:
            if p != character:
                found_primitives |= self.recursively_find_all_primitives(p)
        return set(found_primitives)

    def create_cache(self):

        # (field_name, load_function, column)
        _ = lambda x: x
        requested_fields = [
            ("character", _, "characters.character"),
            #("stroke_count", _, None),
            ("onyomi", j2c, None),
            ("kunyomi", j2c, None),
            ("nanori", j2c, None),
            ("meanings", j2c, None),
            #("frequency_rank", _, None),
            #("grade", _, None),
            #("jlpt", _, None),
            #("kanken", _, None),
            ("primitives", _, None),
            ("primitive_of", _, None),
            ("primitive_keywords", j2c, None),
            ("primitive_alternatives", _, None),
            #("heisig_id5", _, None),
            #("heisig_id6", _, None),
            ("heisig_keyword5", _, None),
            ("heisig_keyword6", _, None),
            ("heisig_story", _, None),
            ("heisig_comment", _, None),
            ("radicals", _, None),
            #("words_default", _, None),
            ("koohi_stories", j2c, None),
            #("wk", _, None),
            ("usr_keyword", _, "usr.keywords.usr_keyword"),
            ("usr_primitive_keyword", _, "usr.keywords.usr_primitive_keyword"),
            ("usr_story", _, "usr.stories.usr_story"),
        ]

        fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

        joins = [
            f"LEFT OUTER JOIN usr.keywords ON characters.character == usr.keywords.character ",
            f"LEFT OUTER JOIN usr.stories ON characters.character == usr.stories.character ",
        ]
        joins_txt = "".join(joins)

        self.crs.execute(
            f"SELECT {fields} FROM characters {joins_txt} "
        )

        raw_data = self.crs.fetchall()

        self.keyword_set_cache = dict()
        self.keyword_cache = dict()
        self.radical_set_cache = dict()
        self.radical_name_set_cache = dict()
        self.radical_name_cache = dict()
        self.primitive_set_cache = dict()
        self.rec_primitive_set_cache = dict()
        self.rec_primitive_name_set_cache = dict()
        self.rec_primitive_name_cache = dict()
        self.reading_set_cache = dict()
        self.reading_cache = dict()
        self.meaning_set_cache = dict()
        self.meaning_cache = dict()
        self.stories_cache = dict()
        self.primitive_alternative_cache = dict()

        if raw_data:
            for raw_row in raw_data:

                # convert json escaping to comma separated value lists
                d = {}
                for data, (name, load_func, _) in zip(raw_row, requested_fields):
                    d[name] = load_func(data) or ''

                c = d['character']

                # create a bunch of caches: sets of values for exact matching and then string
                # representation for partial matching

                # Keywords..
                kw_set= set()
                kw_set.add(d['heisig_keyword5'])
                kw_set.add(d['heisig_keyword6'])
                kw_set.add(d['usr_keyword'])
                kw_set.update(csv_to_list(d['primitive_keywords']))
                kw_set.update(csv_to_list(d['usr_primitive_keyword']))
                if '' in kw_set:
                    kw_set.remove('')
                if len(kw_set)>0:
                    keywords = ','.join(list(kw_set))
                    self.keyword_cache[c] = keywords
                    self.keyword_set_cache[c] = kw_set

                # Primitives..
                if len(d['primitives'])>0:
                    self.primitive_set_cache[c] = set(custom_list(d['primitives']))

                # Radicals..                
                if len(d['radicals'])>0:
                    self.radical_set_cache[c] = set(custom_list(d['radicals']))

                # Readings..
                reading_set= set()
                reading_set.update(csv_to_list(d['onyomi']))
                reading_set.update(csv_to_list(d['kunyomi']))
                reading_set.update(csv_to_list(d['nanori']))
                if '' in reading_set:
                    reading_set.remove('')
                if len(reading_set)>0:
                    readings = ','.join(list(reading_set))
                    self.reading_cache[c] = readings
                    self.reading_set_cache[c] = reading_set

                # Meanings..
                meaning_set= set()
                meaning_set.update(csv_to_list(d['meanings']))
                if '' in meaning_set:
                    meaning_set.remove('')
                if len(meaning_set)>0:
                    self.meaning_cache[c] = d['meanings']
                    self.meaning_set_cache[c] = meaning_set

                # Stories..
                st = set([
                    d['heisig_story'].lower(),
                    d['heisig_comment'].lower(),
                    d['usr_story'].lower(),
                    d['koohi_stories'].lower(),
                    ])
                if '' in st:
                    st.remove('')
                if len(st)>0:
                    self.stories_cache[c] = ','.join(st)

                # create a reverse lookup table for primitive alternatives
                if len(d['primitive_alternatives']) > 0:
                    prim_alt_list = custom_list(d['primitive_alternatives'])
                    for p in prim_alt_list:
                        self.primitive_alternative_cache[p] = c


        # Recursively iterate through a primitives list of each kanji
        # (i.e. create a list of primitives the kanji uses, down to the basic building blocks)
        # With this list create a cache set of primitives, their names and also a free text cache for partial matching
        for c in self.primitive_set_cache.keys():
            rec_primitive_set = self.recursively_find_all_primitives(c)
            if len(rec_primitive_set) > 0:
                rec_primitive_names_set = set()
                for ps in rec_primitive_set:
                    if ps in self.keyword_set_cache:
                        rec_primitive_names_set.update(self.keyword_set_cache[ps])
                    else:
                        print("Note! Kanji %s references primitive %s without a keyword" % (c,ps))

                rec_primitive_names = ','.join(rec_primitive_names_set)
                self.rec_primitive_set_cache[c] = rec_primitive_set
                self.rec_primitive_name_set_cache[c] = rec_primitive_names_set
                self.rec_primitive_name_cache[c] = rec_primitive_names

        # By iterating through a radicals list of each kanji,
        # create a cache set of radical names and also a free text cache for partial matching
        for c,radical_set in self.radical_set_cache.items():
            if len(radical_set) > 0:
                radical_names_set = set()
                for r in radical_set:
                    # some radicals in the list might use slightly different 
                    # (albeit visually indistinguishable) unicode character
                    r = convert_to_correct_unicode_character(r)
                    if r in self.keyword_set_cache:
                        radical_names_set.update(self.keyword_set_cache[r])
                    elif r in self.primitive_alternative_cache:
                        r = self.primitive_alternative_cache[r]
                        radical_names_set.update(self.keyword_set_cache[r])
                    else:
                        if r not in ignore_radicals:
                            print("Note! Kanji %s has unknown radical %s" % (c,r))
                radical_names = ','.join(radical_names_set)
                self.radical_name_set_cache[c] = radical_names_set
                self.radical_name_cache[c] = radical_names

        print("Search engine cache initialization complete!")


    def get_matching_characters(self, search_terms, pool, results, max_results):
        for character, data in pool.items():
            found = True
            for search_term in search_terms:
                if search_term not in data and character != search_term:
                    found = False
            if found:
                if character not in results:
                    results.append(character)
                if len(results)>=max_results:
                    return results
        return results


    def get_matching_characters_with_scoring(self, search_terms, pool, pool_priority, kanji_scores, kanji_matches):
        for character, data in pool.items():
            for search_term in search_terms:
                if search_term in data or character == search_term:
                    if character in kanji_scores:
                        kanji_scores[character] += pool_priority
                        kanji_matches[character].add(search_term)
                    else:
                        kanji_scores[character] = pool_priority
                        kanji_matches[character] = {search_term}


    def get_matching_characters_from_list_of_pools(self, search_terms, pool_list, max_results):

        if len(search_terms) == 1:
            # In the case of only one search term its a simple exhaustive search until enough matches are found. 
            # Search goes through all search pools (keywords, primitive names, free text search) starting
            # from the most prioritized one
            results = []
            for pool_priority, pool in pool_list:
                self.get_matching_characters(search_terms, pool, results, max_results)
                if len(results)>=max_results:
                    return results
            return results

        else:
            # In the case of many search terms it's a bit trickier. We want to give each kanji
            # points - the higher points the more matched search terms in high priority pools
                
            pool_priority = len(pool_list)
            kanji_scores = dict()   # score for each kanji
            kanji_matches = dict() # how many search terms were matched

            for pool_priority, pool in pool_list:
                self.get_matching_characters_with_scoring(search_terms, pool, pool_priority, kanji_scores, kanji_matches)

            # remove those kanjis that didn't match all the search terms
            for kanji, matched_search_terms in kanji_matches.items():
                if len(matched_search_terms) < len(search_terms):
                    kanji_scores.pop(kanji)

            # return only the matching kanjis with highest scoring
            sorted_kanji_scores = sorted(kanji_scores.items(), key=lambda x:x[1], reverse=True)
            sorted_kanji_scores = list(dict(sorted_kanji_scores).keys())
            if len(sorted_kanji_scores) > max_results:
                return sorted_kanji_scores[:max_results]
            
            return sorted_kanji_scores


    def search(self, search_str, max_results=15):

        if search_str == '':
            return []

        # clean up search terms
        search_terms = search_str.split(',')
        if '' in search_terms:
            search_terms.remove('')
        search_terms = [x.strip() for x in search_terms]

        # A list of search pools, each having a distinct priority
        priority_list = [ 
            [30,self.keyword_set_cache],
            [26,self.keyword_cache],
            [20,self.rec_primitive_set_cache], 
            [18,self.rec_primitive_name_set_cache],
            [16,self.rec_primitive_name_cache],
            [14,self.meaning_set_cache],
            [12,self.meaning_cache],
            [10,self.stories_cache],
            [8,self.radical_set_cache],
            [7,self.radical_name_set_cache],
            [6,self.radical_name_cache],
            [5,self.reading_set_cache],
            [4,self.reading_cache],
        ]

        results = self.get_matching_characters_from_list_of_pools(search_terms, priority_list, max_results)

        return list(results)