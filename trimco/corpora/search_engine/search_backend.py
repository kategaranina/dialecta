import math

from pymongo import ASCENDING, DESCENDING

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
        query_parts['annotation.tags'] = {'$all': ann_parts}

    if lemma:
        query_parts['annotation.lemma'] = lemma.lower()

    query = {'words': {'$elemMatch': query_parts}}

    if dialect and any(d for d in dialect):
        query['dialect'] = {'$in': [int(d) for d in dialect]}
    elif not query_parts:
        return

    return query


def search(
        dialect, transcription, standartization, lemma, annotation,
        start_page, prev_page_info, total_pages=None
):
    ascending_sort = [('elan', ASCENDING), ('audio.start', ASCENDING)]
    descending_sort = [('elan', DESCENDING), ('audio.start', DESCENDING)]
    query = compile_query(dialect, transcription, standartization, lemma, annotation)
    results = None
    reverse = False

    if query is not None:
        if 'max' in prev_page_info and start_page - prev_page_info['num'] == 1:  # next page
            limit_query = {
                '$or': [
                    {
                        'elan': {'$eq': prev_page_info['max']['elan']},
                        'audio.start': {'$gt': prev_page_info['max']['audio_start']}
                    },
                    {
                        'elan': {'$gt': prev_page_info['max']['elan']}
                    }
                ]
            }
            query = {'$and': [limit_query, query]}
            results = SENTENCE_COLLECTION.find(query)
            results = results.sort(ascending_sort)
            results = results.limit(MONGODB_LIMIT)

        elif 'min' in prev_page_info and start_page - prev_page_info['num'] == -1:  # prev page
            limit_query = {
                '$or': [
                    {
                        'elan': {'$eq': prev_page_info['min']['elan']},
                        'audio.start': {'$lt': prev_page_info['min']['audio_start']}
                    },
                    {
                        'elan': {'$lt': prev_page_info['min']['elan']}
                    }
                ]
            }
            query = {'$and': [limit_query, query]}
            results = SENTENCE_COLLECTION.find(query)
            results = results.sort(descending_sort)
            results = results.limit(MONGODB_LIMIT)
            reverse = True

        elif total_pages is not None and start_page == int(total_pages):  # last page
            results = SENTENCE_COLLECTION.find(query)
            n_last_page = results.count() % MONGODB_LIMIT or MONGODB_LIMIT
            results = results.sort(descending_sort)
            results = results.limit(n_last_page)
            reverse = True

        else:
            results = SENTENCE_COLLECTION.find(query)
            if start_page > 1:
                results = results.skip((start_page-1) * MONGODB_LIMIT)
            results = results.sort(ascending_sort)
            results = results.limit(MONGODB_LIMIT)

    if total_pages is None and results is not None:
        total_pages = math.ceil(results.count() / MONGODB_LIMIT)
    else:  # do not return total_pages value if we have it as input
        total_pages = None

    result_html, page_info = db_response_to_html(results, reverse=reverse)
    page_info['num'] = start_page

    return result_html, page_info, total_pages


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
