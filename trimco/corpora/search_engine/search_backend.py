from pymongo import ASCENDING

from corpora.utils.db_utils import SENTENCE_COLLECTION
from corpora.utils.elan_utils import ANNOTATION_PART_SEP
from .db_to_html import db_response_to_html, html_to_db
from .elan_to_db import process_one_elan, insert_sentences_in_mongo


def compile_query(dialect, transcription, standartization, lemma, annotation):
    query_parts = {}

    if transcription:
        query_parts['transcription'] = transcription.lower()

    if standartization:
        query_parts['standartization'] = standartization.lower()

    if annotation:
        annotation = annotation.lower().replace(ANNOTATION_PART_SEP, ' ')
        ann_parts = annotation.split()
        query_parts['annotations'] = {'$elemMatch': {'tags': {'$all': ann_parts}}}

    if lemma:
        if 'annotations' not in query_parts:
            query_parts['annotations'] = {'$elemMatch': {}}
        query_parts['annotations']['$elemMatch']['lemma'] = lemma.lower()

    query = {'words': {'$elemMatch': query_parts}}

    if dialect and any(d for d in dialect):
        query['dialect'] = {'$in': [int(d) for d in dialect]}
    elif not query_parts:
        return

    return query


def search(dialect, transcription, standartization, lemma, annotation):
    query = compile_query(dialect, transcription, standartization, lemma, annotation)
    results = SENTENCE_COLLECTION.find(query) if query is not None else None
    if results is not None:
        results = results.sort([('elan', ASCENDING), ('audio.start', ASCENDING)])
    result_html = db_response_to_html(results)
    return result_html


def saved_recording_to_db(eaf_path, audio_path, html, dialect):
    eaf_filename = eaf_path.rsplit('/', 1)[-1]
    audio_filename = audio_path.rsplit('/', 1)[-1]

    query = {'elan': eaf_filename}
    match = SENTENCE_COLLECTION.find_one(query)

    if match is not None:
        html_to_db(html)
    else:
        sentences = process_one_elan(eaf_filename, audio_filename, dialect)
        insert_sentences_in_mongo(sentences)
