import sqlite3
import json
import sys
import os
import logging
from collections import OrderedDict

LINE_FORMAT_SHORT = 0
LINE_FORMAT_LONG = 1

def fw(args):
    if "\t" in "".join(args):
        raise ValueError("TSV ERROR")

    s = "\t".join(args) + '\n'
    return s

processed_line_dict = OrderedDict()

comment_number = 0

total_changes = 0
line_number = 0

line_format = None

ext_tsv_path = sys.argv[1] if len(sys.argv) > 1 else "kanji-patch-6.tsv"
clean_tsv_path = sys.argv[2] if len(sys.argv) > 2 else "cleaned.tsv"

f = open(clean_tsv_path, "w", encoding="utf-8")

for l in open(ext_tsv_path, "r", encoding="utf-8"):
    
    line_number += 1

    d = l.replace("\n", "").split("\t")
    if len(d[0]) == 0:
        logging.info("")
        continue
    if d[0] == 'Kanji' or d[0] == 'character':
        # process the header
        if d[:4] == ['Kanji','Field','OldValue','NewValue']:
            # File consists of 1 change per line
            line_format = LINE_FORMAT_SHORT
            if len(d) == 5:
                if d[4] != 'Comment':
                    raise Exception("Error in file format!")
                comment_field_enabled = True
            else:
                if len(d) != 4:
                    raise Exception("Error in file format!")
        else:
            raise Exception("not supported")
        processed_line_dict['header',''] = fw(d)
        continue
    if d[0][0]=='#':  # only log the comments
        # modify the comments so they look better in markdown
        hash_count = d[0].count('#')
        cleaned_comment = d[0].replace('#', '')
        if hash_count > 5:
            logging.info('----')
            comment = '## ' + cleaned_comment
        elif hash_count > 1:
            comment = '###' + cleaned_comment
        else:
            comment = '####' + cleaned_comment
        processed_line_dict['','comment_' + str(comment_number)] = fw(d)
        comment_number += 1
        continue
    if d[1] == 'DELETE':
        processed_line_dict['','comment_' + str(comment_number)] = fw(d)
        comment_number += 1
        continue

    if line_format == LINE_FORMAT_SHORT:
        if len(d) == 5 and comment_field_enabled:
            comment_field = d[4]
        else:
            if len(d) != 4:
                raise Exception("Error! Line %d - wrong length in data: %s" % (line_number, str(d)))
            comment_field = ''

        previous_value = d[2]
        # this is the new [character,new value] pair
        #d = [d[0],d[3]]
    else:
        raise Exception("Error! No header defined!")

    kanji = d[0].strip()
    
    character_field_tuple = (kanji,d[1])

    if character_field_tuple in processed_line_dict:
        print("Overwriting",character_field_tuple)
    processed_line_dict[character_field_tuple] = fw(d)


for (character,field), data in processed_line_dict.items():
    f.write(data)


f.close()

