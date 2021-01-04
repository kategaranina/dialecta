import re
from collections import defaultdict

from pympi import Eaf

from .misc import (
    ANNOTATION_WORD_SEP, ANNOTATION_OPTION_SEP,
    WORD_COLLECTION, STANDARTIZATION_COLLECTION,
    clean_transcription
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

            words['words'][word].add(std)
            for ann in anns:
                words['standartizations'][std].append(ann)

    return words


def reformat_words_for_db(words):
    new_words = {
        'words': [{'word': k, 'standartizations': list(v)} for k, v in words['words'].items()],
        'standartizations': [{'word': k, 'annotations': v} for k, v in words['standartizations'].items()],
    }
    return new_words


def process_one_elan(eaf_filename):
    eaf_obj = Eaf(eaf_filename)
    words = {
        'words': defaultdict(set),
        'standartizations': defaultdict(list)
    }

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


def insert_one_word_in_mongo(word, standartizations):
    WORD_COLLECTION.find_one_and_update(
        {'word': word},
        {'$addToSet': {'standartizations': {'$each': standartizations}}},
        upsert=True
    )


def insert_one_standartization_in_mongo(standartization, annotations):
    STANDARTIZATION_COLLECTION.find_one_and_update(
        {'word': standartization},
        {'$push': {'annotations': {'$each': annotations}}},
        upsert=True
    )


def insert_words_in_mongo(words):
    for word_info in words['words']:
        insert_one_word_in_mongo(word_info['word'], word_info['standartizations'])

    for st_info in words['standartizations']:
        insert_one_standartization_in_mongo(st_info['word'], st_info['annotations'])


def insert_manual_annotation_in_mongo(word, standartization, lemma, grammar):
    standartization = standartization.lower()
    annotation = lemma.lower() + '-' + grammar
    insert_one_word_in_mongo(word.lower(), [standartization])
    insert_one_standartization_in_mongo(standartization, [annotation])


def find_word(word):
    return WORD_COLLECTION.find_one({'word': word})


def find_standartization(word):
    return STANDARTIZATION_COLLECTION.find_one({'word': word})
