from collections import defaultdict

from pympi import Eaf

from .db_utils import WORD_COLLECTION, STANDARTIZATION_COLLECTION
from .elan_utils import (
    clean_transcription, get_tier_alignment,
    get_annotation_alignment
)
from .format_utils import (
    ANNOTATION_OPTION_SEP, ANNOTATION_TAG_SEP,
    STANDARTIZATION_REGEX, STANDARTIZATION_NUM_REGEX,
    ANNOTATION_NUM_REGEX
)


def process_one_tier(eaf_filename, words, orig_tier, standartization_tier, annotation_tier):
    tier_alignment = get_tier_alignment(orig_tier, standartization_tier, annotation_tier)
    for orig, standartization, annotation in tier_alignment.values():
        standartizations = get_annotation_alignment(standartization, num_regex=STANDARTIZATION_NUM_REGEX)
        annotations = get_annotation_alignment(annotation, num_regex=ANNOTATION_NUM_REGEX)

        for i, word in enumerate(clean_transcription(orig).split()):
            std = standartizations.get(i)
            if std is None:
                print('WARNING: ' + eaf_filename, 'no std for word ' + str(i), orig, standartization, '', sep='\n')
                continue

            words['words'][word].append(std)

            ann = annotations.get(i)
            if ann is None:
                print('WARNING: ' + eaf_filename, 'no ann for word ' + str(i), orig, annotation, '', sep='\n')
                continue

            words['standartizations'][std].append(ann)

    return words


def reformat_words_for_db(words, model_name):
    new_words = {
        'words': [
            {'word': k, 'model': model_name, 'standartizations': list(v)}
            for k, v in words['words'].items()
        ],
        'standartizations': [
            {'word': k, 'model': model_name, 'annotations': v}
            for k, v in words['standartizations'].items()
        ]
    }
    return new_words


def process_one_elan(eaf_filename, model_name):
    eaf_obj = Eaf(eaf_filename)
    words = {
        'words': defaultdict(list),
        'standartizations': defaultdict(list)
    }

    for tier_name, tier in eaf_obj.tiers.items():
        standartization_tier_name = STANDARTIZATION_REGEX.search(tier_name)
        if standartization_tier_name is None:
            continue

        speaker = standartization_tier_name.group(1)
        try:
            orig_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker), key=lambda x: x[0])
            standartization_tier = sorted(eaf_obj.get_annotation_data_for_tier(tier_name), key=lambda x: x[0])
            annotation_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker + '_annotation'), key=lambda x: x[0])
        except KeyError:
            print('ERROR: ' + eaf_filename + ': lacking tiers for ' + speaker)
            continue

        words = process_one_tier(eaf_filename, words, orig_tier, standartization_tier, annotation_tier)

    return reformat_words_for_db(words, model_name)


def insert_one_word_in_mongo(word, model, standartizations):
    WORD_COLLECTION.find_one_and_update(
        {'word': word, 'model': model},
        {'$push': {'standartizations': {'$each': standartizations}}},
        upsert=True
    )


def insert_one_standartization_in_mongo(standartization, model, annotations):
    STANDARTIZATION_COLLECTION.find_one_and_update(
        {'word': standartization, 'model': model},
        {'$push': {'annotations': {'$each': annotations}}},
        upsert=True
    )


def insert_words_in_mongo(words):
    for word_info in words['words']:
        insert_one_word_in_mongo(
            word_info['word'],
            word_info['model'],
            word_info['standartizations']
        )

    for st_info in words['standartizations']:
        insert_one_standartization_in_mongo(
            st_info['word'],
            st_info['model'],
            st_info['annotations']
        )


def insert_manual_annotation_in_mongo(model, word, standartization, lemma, grammar):
    standartization = standartization.lower()
    annotation = lemma.lower() + ANNOTATION_TAG_SEP + grammar
    insert_one_word_in_mongo(word.lower(), model, [standartization])
    insert_one_standartization_in_mongo(standartization, model, [annotation])


def find_word(word, model):
    return WORD_COLLECTION.find_one({'word': word, 'model': model})


def find_standartization(word, model):
    return STANDARTIZATION_COLLECTION.find_one({'word': word, 'model': model})
