import re
from collections import defaultdict

from pympi import Eaf

from .misc import (
    ANNOTATION_WORD_SEP, ANNOTATION_OPTION_SEP,
    WORD_COLLECTION, STANDARTIZATION_COLLECTION,
    clean_transcription
)


standartization_regex = re.compile(r'^(.+?)_standartization$')
standartization_num_regex = re.compile(r'^(\d+):(.+)')
annotation_num_regex = re.compile(r'(\d+?):.+?:(.+)')


def get_tier_alignment(orig_tier, standartization_tier, annotation_tier):
    tier_alignment = {(ann[0], ann[1]): [ann[2], None, None] for ann in orig_tier}

    for ann in standartization_tier:
        if (ann[0], ann[1]) in tier_alignment:
            tier_alignment[(ann[0], ann[1])][1] = ann[2]

    for ann in annotation_tier:
        if (ann[0], ann[1]) in tier_alignment:
            tier_alignment[(ann[0], ann[1])][2] = ann[2]

    return tier_alignment


def process_one_tier(eaf_filename, words, orig_tier, standartization_tier, annotation_tier):
    tier_alignment = get_tier_alignment(orig_tier, standartization_tier, annotation_tier)
    for orig, standartization, annotation in tier_alignment.values():
        if standartization is None or annotation is None:
            continue

        standartizations = {}
        for std in standartization.split(ANNOTATION_WORD_SEP):
            std_num, std = standartization_num_regex.search(std).groups()
            standartizations[int(std_num)] = std

        annotations = {}
        for ann in annotation.split(ANNOTATION_WORD_SEP):
            ann_num, ann = annotation_num_regex.search(ann).groups()
            annotations[int(ann_num)] = ann

        for i, word in enumerate(clean_transcription(orig).split()):
            std = standartizations.get(i)
            if std is None:
                print('WARNING: ' + eaf_filename, 'no std for word ' + str(i), orig, standartization, '', sep='\n')
                continue

            words['words'][word].append(std)

            anns = annotations.get(i)
            if anns is None:
                print('WARNING: ' + eaf_filename, 'no ann for word ' + str(i), orig, annotation, '', sep='\n')
                continue

            anns = anns.split(ANNOTATION_OPTION_SEP)
            for ann in anns:
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
        standartization_tier_name = standartization_regex.search(tier_name)
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
    annotation = lemma.lower() + '-' + grammar
    insert_one_word_in_mongo(word.lower(), model, [standartization])
    insert_one_standartization_in_mongo(standartization, model, [annotation])


def find_word(word, model):
    return WORD_COLLECTION.find_one({'word': word, 'model': model})


def find_standartization(word, model):
    return STANDARTIZATION_COLLECTION.find_one({'word': word, 'model': model})
