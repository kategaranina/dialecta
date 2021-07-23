import math

from pymongo import ASCENDING

from trimco.settings import MONGODB_LIMIT
from corpora.utils.db_utils import SENTENCE_COLLECTION
from corpora.utils.format_utils import ANNOTATION_TAG_SEP
from .db_to_html import db_response_to_html, html_to_db
from .elan_to_db import process_one_elan, insert_sentences_in_mongo


def compile_query(dialect, transcription, standartization, lemma, annotation):
    query_parts = {}

    if transcription:
        query_parts['transcription'] = transcription.lower()

    if standartization:
        query_parts['standartization'] = standartization.lower()

    if annotation:
        annotation = annotation.lower().replace(ANNOTATION_TAG_SEP, ' ')
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


def search(dialect, transcription, standartization, lemma, annotation, start_page, return_total_pages=False):
    query = compile_query(dialect, transcription, standartization, lemma, annotation)
    results = None
    total_pages = None

    if query is not None:
        results = SENTENCE_COLLECTION.find(query)
        if start_page > 1:
            results = results.skip((start_page-1) * MONGODB_LIMIT)
        results = results.limit(MONGODB_LIMIT)
        results = results.sort([('elan', ASCENDING), ('audio.start', ASCENDING)])

        if return_total_pages:
            total_pages = math.ceil(results.count() / MONGODB_LIMIT)

    result_html = db_response_to_html(results)
    return result_html, total_pages


def saved_recording_to_db(eaf_path, audio_path, html, dialect):
    eaf_filename = eaf_path.rsplit('/', 1)[-1]
    audio_filename = audio_path.rsplit('/', 1)[-1]

    query = {'elan': eaf_filename}
    match = SENTENCE_COLLECTION.find_one(query)
    print('nya1')

    if match is not None:
        html_to_db(html)
    else:
        sentences = process_one_elan(eaf_filename, audio_filename, dialect)
        insert_sentences_in_mongo(sentences)
    print('nya2')
