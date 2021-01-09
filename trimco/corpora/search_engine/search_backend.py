from corpora.utils.db_utils import SENTENCE_COLLECTION


def compile_query(dialect, transcription, standartization, lemma, annotation):
    query_parts = {}

    if dialect:
        query_parts['dialect'] = dialect

    if transcription:
        query_parts['transcription'] = transcription

    if standartization:
        query_parts['standartization'] = standartization

    if lemma:
        query_parts['lemmata'] = {'$in': [lemma]}

    if annotation:
        annotation = annotation.replace('-', ' ')
        ann_parts = annotation.split()
        query_parts['annotations'] = {'$elemMatch': {'tags': {'$all': ann_parts}}}

    query = {'words': {'$elemMatch': query_parts}}
    return query


def search(transcription, standartization, lemma, annotation):
    query = compile_query(transcription, standartization, lemma, annotation)
    results = SENTENCE_COLLECTION.find(query)
    return results
