import sys
sys.path.append('..')

import os
import sqlite3

from corpora.utils.word_list import process_one_elan, insert_words_in_mongo


conn = sqlite3.connect('../db.sqlite3')
c = conn.cursor()

media_dir = '../data/media/'


def get_recordings():
    recs = c.execute("""
        SELECT data, to_dialect_id 
        FROM corpora_recording 
        WHERE checked = 1
    """).fetchall()
    return recs


def get_dialect_to_model_mapping():
    raw_mapping = c.execute("""
        SELECT dialect_id, model_id 
        FROM normalization_model_to_dialect 
    """).fetchall()
    return dict(raw_mapping)


def get_models():
    models = c.execute("""
        SELECT id, name 
        FROM normalization_model
    """).fetchall()
    return dict(models)


def insert_wordlist():
    recs = get_recordings()
    models = get_models()
    dialect_to_model_mapping = get_dialect_to_model_mapping()

    for rec in recs:
        print(rec)
        rec_path = os.path.join(media_dir, rec[0])

        model_id = dialect_to_model_mapping.get(rec[1])
        if model_id is None:
            print('ERROR: ' + rec_path + ': no model for chosen dialect')
            continue

        print(rec_path)

        try:
            model_name = models[model_id]
            words = process_one_elan(rec_path, model_name)
            insert_words_in_mongo(words)
        except Exception as e:
            print('ERROR', e)
            print()


if __name__ == '__main__':
    insert_wordlist()
