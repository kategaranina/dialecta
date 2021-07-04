import sqlite3

from corpora.search_engine.elan_to_db import process_one_elan, insert_sentences_in_mongo


conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()


def get_recordings():
    recs = c.execute("""
        SELECT data, audio, to_dialect_id 
        FROM corpora_recording 

    """).fetchall()
    return recs


def insert_sentences():
    recs = get_recordings()
    sentences = []

    for rec in recs:
        eaf_filename, audio_filename, dialect = rec
        eaf_filename = eaf_filename.rsplit('/', 1)[-1]
        audio_filename = audio_filename.rsplit('/', 1)[-1]
        curr_sentences = process_one_elan(eaf_filename, audio_filename, dialect)
        sentences.extend(curr_sentences)
    if sentences:
        insert_sentences_in_mongo(sentences)


if __name__ == '__main__':
    insert_sentences()
