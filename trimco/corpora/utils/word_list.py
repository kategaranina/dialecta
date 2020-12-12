import re
from collections import defaultdict

from pympi import Eaf

from .misc import (
    ANNOTATION_WORD_SEP, ANNOTATION_OPTION_SEP,
    WORD_COLLECTION, clean_transcription
)


standartization_regex = re.compile(r'^(.+?)_standartization$')
standartization_num_regex = re.compile(r'^\d+:')
annotation_filtering_regex = re.compile(r'.+?:.+?:')


def process_one_tier(eaf_filename, words, orig_tier, standartization_tier, annotation_tier):
    for orig, standartization, annotation in zip(orig_tier, standartization_tier, annotation_tier):
        orig_words = clean_transcription(orig[2]).split()
        standartizations = standartization[2].split(ANNOTATION_WORD_SEP)
        annotations = annotation[2].split(ANNOTATION_WORD_SEP)
        eq_length = len(orig_words) == len(standartizations) == len(annotations)
        if not eq_length:
            print(
                'ERROR: ' + eaf_filename + ': mismatch between orig sentence and annotation.' +
                ' Orig length', len(orig_words),
                ' Standartization length', len(standartizations),
                ' Annotation length', len(annotations)
            )
            continue

        for word, std, anns in zip(orig_words, standartizations, annotations):
            std = standartization_num_regex.sub('', std)
            anns = annotation_filtering_regex.sub('', anns)
            anns = anns.split(ANNOTATION_OPTION_SEP)
            for ann in anns:
                words[word][std].add(ann)

    return words


def reformat_words_for_db(words):
    new_words = [
        {
            'word': word,
            'standartization': [
                {
                    'word': standartization,
                    'annotation': list(annotation)
                }
                for standartization, annotation in word_info.items()
            ]
        }
        for word, word_info in words.items()
    ]
    return new_words


def process_one_elan(eaf_filename):
    eaf_obj = Eaf(eaf_filename)
    words = defaultdict(lambda: defaultdict(set))

    for tier_name, tier in eaf_obj.tiers.items():
        standartization_tier_name = standartization_regex.search(tier_name)
        if standartization_tier_name is None:
            continue

        speaker = standartization_tier_name.group(1)
        orig_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker), key=lambda x: x[0])
        standartization_tier = sorted(eaf_obj.get_annotation_data_for_tier(tier_name), key=lambda x: x[0])
        annotation_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker + '_annotation'), key=lambda x: x[0])

        words = process_one_tier(eaf_filename, words, orig_tier, standartization_tier, annotation_tier)

    return reformat_words_for_db(words)


def insert_words_in_mongo(words):
    for word_info in words:
        word_in_db = WORD_COLLECTION.find_one({'word': word_info['word']}, {'_id': 1})
        if word_in_db is None:
            WORD_COLLECTION.insert_one(word_info)
            continue

        word_id = word_in_db['_id']
        for standartization in word_info['standartization']:
            standartization_in_word = WORD_COLLECTION.find_one({
                '_id': word_id,
                'standartization.word': standartization['word']
            })
            if standartization_in_word is None:
                WORD_COLLECTION.update_one(
                    {'_id': word_id},
                    {'$push': {'standartization': standartization}}
                )
                continue

            WORD_COLLECTION.update_one(
                {'_id': word_id, 'standartization.word': standartization['word']},
                {'$addToSet': {'standartization.$.annotation': {'$each': standartization['annotation']}}}
            )
