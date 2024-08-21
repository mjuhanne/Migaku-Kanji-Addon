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

# (field_name, load_function, column)
_ = lambda x: x
requested_fields = [
    ("character", _, "characters.character"),
    #("stroke_count", _, None),
    ("onyomi", j2c, None),
    ("kunyomi", j2c, None),
    ("nanori", j2c, None),
    ("meanings", j2c, None),
    ("frequency_rank", _, None),
    #("grade", _, None),
    #("jlpt", _, None),
    ("kanken", _, None),
    ("radicals", _, None),
    ("usr_keyword", _, "usr.keywords.usr_keyword"),
    ("usr_primitive_keyword", _, "usr.keywords.usr_primitive_keyword"),
    ("usr_story", _, "usr.stories.usr_story"),
]

sql_fields = ",".join((rf[2] if rf[2] else rf[0]) for rf in requested_fields)

joins = [
    f"LEFT OUTER JOIN usr.keywords ON characters.character == usr.keywords.character ",
    f"LEFT OUTER JOIN usr.stories ON characters.character == usr.stories.character ",
]
sql_joins_txt = "".join(joins)

# this table links radicals to their Heisig primitive counterpart to allow for
# even better search capability
# (some of them have identical visual look but differ only in Unicode)
unicode_conversion_table = {
    'ノ' : '丿',
    '｜' : '丨',
    '⺅' : '亻',
    '⺾' : '艹',
    '爿' : '丬',
    '辶' : '辶',
}

class SearchEngine:

    def __init__(self, parent):
        self.parent = parent
        self.crs = parent.crs

        # These search pools consists of sets/lists of values for exact matching and then 
        # their string representation to enable fast partial matching.
        self.keyword_set_cache = dict()
        self.keyword_cache = dict()
        self.radical_set_cache = dict()
        self.radical_name_set_cache = dict()
        self.radical_name_cache = dict()
        self.rec_radical_set_cache = dict()
        self.primitive_list_cache = dict()
        self.rec_primitive_list_cache = dict()
        self.rec_primitive_name_list_cache = dict()
        self.rec_primitive_name_cache = dict()
        self.reading_set_cache = dict()
        self.reading_cache = dict()
        self.meaning_set_cache = dict()
        self.meaning_cache = dict()
        self.stories_cache = dict()
        self.radicals_set = set()
        self.priority = dict()
        self.character_list = []

        self.init_cache()

    def radical_to_primitive(self,r, fetch_primary_primitive=True):
        # First do unicode conversion because some radicals in the list might use slightly
        # # different (albeit visually indistinguishable) unicode character.
        if r in unicode_conversion_table:
            r = unicode_conversion_table[r]
        # .. then reference the main primitive instead if this is an alternative primitive
        if fetch_primary_primitive:
            r = self.parent.story_db.get_primary_primitive_from_alternative(r)
        return r

    def recursively_find_all_primitives(self, character):
        if character not in self.primitive_list_cache:
            # return at least auto-reference
            return [character]
        primitives = self.primitive_list_cache[character]
        if len(primitives) == 1 and character in primitives:
            # skip all the primitives that have only themselves listed as primitives
            return [character]
        found_primitives = primitives.copy()
        # recursively find all primitives
        for p in primitives:
            if p != character:
                new_primitives = self.recursively_find_all_primitives(p)
                for np in new_primitives:
                    # in the case a kanji has multiples of the same primitive (eg. mouth)
                    # we want all the parent kanjis to have at least the same amount
                    if found_primitives.count(np) < new_primitives.count(np):
                        found_primitives.append(np)
        return found_primitives

    def recursively_find_all_radicals(self, character):
        if character in self.radicals_set:
            return set(character)
        if character in self.radical_set_cache:
            radicals = set(self.radical_set_cache[character])
        else:
            radicals = set()
        # recursively find all radicals that this kanji or its primitives uses
        if character in self.primitive_list_cache:
            for p in self.primitive_list_cache[character]:
                if p != character:
                    new_radicals = self.recursively_find_all_radicals(p)
                    radicals.update(new_radicals)
        return radicals

    def update_recursive_primitive_cache(self,character):
        rec_primitive_list = self.recursively_find_all_primitives(character)
        if len(rec_primitive_list) > 0:
            rec_primitive_names_list = list()
            for p in rec_primitive_list:
                if p in self.keyword_set_cache:
                    kw_set = self.keyword_set_cache[p]
                    for kw in kw_set:
                        rec_primitive_names_list.append(kw)
                else:
                    print("Note! Kanji %s references primitive %s without a keyword" % (character,p))

            rec_primitive_names = ','.join(rec_primitive_names_list)
            self.rec_primitive_list_cache[character] = rec_primitive_list
            self.rec_primitive_name_list_cache[character] = rec_primitive_names_list
            self.rec_primitive_name_cache[character] = rec_primitive_names

    def init_cache(self):
        self.update_cache()

        # By iterating through a radicals list of each kanji
        # create a set of radical names for exact matching and also a free text
        # cache for partial matching
        for c,radical_set in self.radical_set_cache.items():
            if len(radical_set) > 0:
                radical_names_set = set()
                for r in radical_set:
                    # We want to get keywords from the associated primitive
                    r = self.radical_to_primitive(r)
                    if r in self.keyword_set_cache:
                        radical_names_set.update(self.keyword_set_cache[r])
                radical_names = ','.join(radical_names_set)
                self.radical_name_set_cache[c] = radical_names_set
                self.radical_name_cache[c] = radical_names

        print("Search engine cache initialization complete!")

    # Update cache for a character. If character is None, then update cache for all characters
    def update_cache(self, character=None):
        print("Updating search engine cache..")

        if character:
            self.crs.execute(
                f"SELECT {sql_fields} FROM characters {sql_joins_txt} WHERE characters.character=?",
                (character,),
            )
        else:
            self.crs.execute(
                f"SELECT {sql_fields} FROM characters {sql_joins_txt} " 
            )

        raw_data = self.crs.fetchall()

        if raw_data:
            for raw_row in raw_data:

                # convert json escaping to python data structures (strings, lists)
                d = {}
                for data, (name, load_func, _) in zip(raw_row, requested_fields):
                    d[name] = load_func(data) or ''

                c = d['character']
                self.character_list.append(c)

                # Radicals..
                if len(d['radicals'])>0:
                    self.radical_set_cache[c] = set(custom_list(d['radicals']))
                    self.radicals_set |= self.radical_set_cache[c]

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

                # User stories..
                self.stories_cache[c] = d['usr_story'].lower()

                # User keyword..
                kw_set = set()
                kw_set.add(d['usr_keyword'].lower())
                kw_set.add(d['usr_primitive_keyword'].lower())
                kw_set.discard('')
                if len(kw_set)>0:
                    self.keyword_cache[c] = ','.join(list(kw_set))
                    self.keyword_set_cache[c] = kw_set

                # Calculate kanji priority based on its frequency and Kanken grading
                points = 0
                if d['frequency_rank'] is not None and d['frequency_rank'] != '':
                    fr_points = (4000 - d['frequency_rank'])/400
                    if fr_points <= 0:
                        fr_points = 0
                    points += fr_points
                if d['kanken'] is not None and d['kanken'] != '':
                    points += 11 - float(d['kanken'])
                self.priority[c] = points

        # Process data from separate story database
        stories_per_source_and_kanji = self.parent.story_db.get_stories(character)

        for key, elements in stories_per_source_and_kanji.items():
            
            if character is None:
                (source, c) = key
            else:
                source = key
                c = character
            
            # Stories and comments..
            story_text = ' '.join(elements['story']) + ' '.join(elements['comment'])
            if c in self.stories_cache:
                self.stories_cache[c] += ' ' + story_text
            else:
                self.stories_cache[c] = ' ' + story_text            

            # Keywords..
            kw_set = set([k.lower() for k in elements['keywords']])
            kw_set.update([k.lower() for k in elements['primitive_keywords']])
            kw_set.discard('')
            if len(kw_set)>0:
                if c in self.keyword_set_cache:
                    self.keyword_set_cache[c].update(kw_set)
                else:
                    self.keyword_set_cache[c] = kw_set
            
            # Primitives..
            p_list = elements['primitives']
            if len(p_list)>0:
                if c in self.primitive_list_cache:
                    for p in p_list:
                        # in the case a kanji has multiples of the same primitive (eg. mouth)
                        # we want to retain the maximum amount
                        if self.primitive_list_cache[c].count(p) < p_list.count(p):
                            self.primitive_list_cache[c].append(p)
                else:
                    self.primitive_list_cache[c] = p_list

                # Update priority of those primitives that this kanji uses
                for p in p_list:
                    primary_p = self.parent.story_db.get_primary_primitive_from_alternative(p)
                    if primary_p is not None:
                        p = primary_p
                    self.priority[p] += 1

        for c, kw_set in self.keyword_set_cache.items():
            self.keyword_cache[c] = ','.join(list(kw_set))

        # Create a search pool based on all the radicals each kanji (and all its primitives) use
        if not character:
            for c in self.character_list:
                self.rec_radical_set_cache[c] = self.recursively_find_all_radicals(c)

        # Recursively iterate through a primitives list of each kanji
        # (i.e. create a list of primitives the kanji uses, down to the basic building blocks)
        # With this list create a cache set of primitives, their names and also a free text cache for partial matching
        if not character:
            for c in self.primitive_list_cache.keys():
                self.update_recursive_primitive_cache(c)
        else:
            if character in self.primitive_list_cache.keys():
                self.update_recursive_primitive_cache(c)


    # select only appropriate search terms for this pool to prevent
    # unnecessary long searches
    def filter_search_terms_for_pool(self, search_terms, pool_settings ):
        filtered_search_terms = dict()
        (pool_priority, is_set, class_list) = pool_settings
        for (search_term,search_class),required_count in search_terms.items():
            if is_set and required_count>1:
                # we want more than 1 occurence but this is a set -> ignore this term
                continue
            if search_class is not None and search_class not in class_list:
                # the given search class (e.g. 'p' for primitive) doesn't match this pool
                continue
            filtered_search_terms[(search_term,search_class)] = required_count
        return filtered_search_terms


    def get_matching_characters(self, search_terms, pool, pool_settings, results, max_results, ignore_obsolete_kanjis):

        for character, data in pool.items():
            found = True
            if ignore_obsolete_kanjis and self.priority[character] == 0:
                found = False
            else:
                if character == '縄':
                    pass
                for (search_term,search_class), required_count in search_terms.items():
                    if required_count>1:
                        if data.count(search_term) < required_count:
                            found = False
                    else:
                        if search_term not in data and character != search_term:
                            found = False
            if found:
                if character not in results:
                    results.append(character)
                if len(results)>=max_results:
                    return results
        return results


    def get_matching_characters_with_scoring(self, search_terms, pool, pool_settings, kanji_scores, kanji_matches, ignore_obsolete_kanjis):
        (pool_priority, is_set, class_list) = pool_settings

        for character, data in pool.items():

            if not ignore_obsolete_kanjis or self.priority[character] > 0:
                for search_tuple, required_count in search_terms.items():
                    (search_term, search_class) = search_tuple
                    found = False
                    if required_count>1:
                        if data.count(search_term) >= required_count:
                            found = True
                    else:
                        if search_term in data or character == search_term:
                            found = True

                    if found:
                        if character in kanji_scores:
                            kanji_scores[character] += pool_priority
                            kanji_matches[character].add(search_tuple)
                        else:
                            kanji_scores[character] = pool_priority
                            kanji_matches[character] = {search_tuple}
                        if character in self.priority:
                            kanji_scores[character] += self.priority[character]


    def get_matching_characters_from_list_of_pools(self, search_terms, pool_list, max_results, ignore_obsolete_kanjis):

        if len(search_terms) == 1:
            # In the case of only one search term its a simple exhaustive search until enough matches are found. 
            # Search goes through all search pools (keywords, primitive names, free text search) starting
            # from the most prioritized one
            results = []
            for pool, pool_settings in pool_list:
                filtered_search_terms = self.filter_search_terms_for_pool(search_terms, pool_settings)
                if len(filtered_search_terms)>0:
                    self.get_matching_characters(filtered_search_terms, pool, pool_settings, results, max_results, ignore_obsolete_kanjis)
                if len(results)>=max_results:
                    return results
            return results

        else:
            # In the case of many search terms it's a bit trickier. We want to give each kanji
            # points - the higher points the more matched search terms in high priority pools
            kanji_scores = dict()   # score for each kanji
            kanji_matches = dict() # how many search terms were matched

            for pool, pool_settings in pool_list:
                filtered_search_terms = self.filter_search_terms_for_pool(search_terms, pool_settings)
                if len(filtered_search_terms)>0:
                    self.get_matching_characters_with_scoring(filtered_search_terms, pool, pool_settings, kanji_scores, kanji_matches, ignore_obsolete_kanjis)

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


    def search(self, search_str, max_results=15, ignore_obsolete_kanjis=False):

        if search_str == '':
            return []

        # clean up search terms
        search_terms_list = search_str.split(',')
        if '' in search_terms_list:
            search_terms_list.remove('')
        search_terms_list = [x.strip() for x in search_terms_list]

        # parse search term modifiers
        search_terms_dict = dict()
        for term in search_terms_list:
            search_class = None
            multiplier = 1
            # check for search class (primitive, radical, story) modifier
            if ':' in term:
                elements = term.split(':')
                if len(elements)==2:
                    search_class = elements[0]
                    term = elements[1]
                else:
                    # incomplete/invalid search term
                    term = None

            # check for 'required occurrence multiplier' modifier
            if '*' in term:
                elements = term.split('*')
                if len(elements)==2:
                    try:
                        elements = [x.strip() for x in elements]
                        if elements[0].isdigit():
                            term = elements[1]
                            multiplier = int(elements[0])
                        elif elements[1].isdigit():
                            term = elements[0]
                            multiplier = int(elements[1])
                    except:
                        # incomplete/invalid search term
                        term = None

            search_tuple = (term,search_class)
            if search_tuple in search_terms_dict:
                search_terms_dict[search_tuple] += multiplier
            else:
                search_terms_dict[search_tuple] = multiplier
                
        # A list of search pools, each having a distinct priority 
        # and a search class (keyword, meaning, primitive, story, radical, reading)
        priority_list = [ 
            [self.keyword_set_cache,    (30,True,['k'])],
            [self.keyword_cache,        (26,False,['k'])],

            [self.meaning_set_cache,    (20,True,['m'])],
            [self.meaning_cache,        (18,False,['m'])],

            [self.rec_primitive_list_cache,     (16,False,['p'])], 
            [self.rec_primitive_name_list_cache,(14,False,['p'])],
            [self.rec_primitive_name_cache,     (12,False,['p'])],

            [self.stories_cache,            (10,False,['s'])],
            [self.radical_set_cache,        (8,True,['r'])],
            [self.radical_name_set_cache,   (7,True,['r'])],
            [self.radical_name_cache,       (6,False,['r'])],
            [self.reading_set_cache,        (5,True,['re'])],
            [self.reading_cache,            (4,False,['re'])],
        ]

        results = self.get_matching_characters_from_list_of_pools(search_terms_dict, priority_list, max_results, ignore_obsolete_kanjis)
        results = self.parent.story_db.add_alternative_primitives_to_list(list(results), True)
        if len(results) > max_results:
            results = results[:max_results]
        return list(results)
    

    # Suggest primitives based on 
    def suggest_primitives(self, target_character, max_results=15):

        input_radicals = self.parent.get_field(target_character,"radicals")
        
        match_scores = dict()
        # find primitives that have all the radicals used by target kanji character
        for c,radicals in self.rec_radical_set_cache.items():
            if c in input_radicals:
                # We always want to add the input radicals themselves in the matching list.
                # The whole list is not added because there might be some radicals
                # which aren't referencable primitives themselves
                match_scores[c] = 10
            else:
                if len(radicals)>len(input_radicals) or len(radicals)==0:
                    continue
                if c == target_character:
                    continue
                found = True
                for r in radicals:
                    if r not in input_radicals:
                        found= False
                if found:
                    match_scores[c] = len(radicals)

        # give higher priority to those primitives that have the highest amount of matching radicals
        sorted_match_scores = sorted(match_scores.items(), key=lambda x:x[1], reverse=True)
        sorted_matches = list(dict(sorted_match_scores).keys())

        # clean the list and add all alternative primitives
        sorted_matches = [ self.radical_to_primitive(r, False) for r in sorted_matches]
        sorted_matches = self.parent.story_db.add_alternative_primitives_to_list(sorted_matches)

        if len(sorted_matches) > max_results:
            return sorted_matches[:max_results]

        return sorted_matches
    