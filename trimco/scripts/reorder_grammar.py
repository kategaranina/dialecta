import sys
sys.path.append('..')

import re
import os
import json
from collections import defaultdict, Counter

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trimco.settings")
django.setup()

import sqlite3
import pymorphy2
from pympi import Eaf

from corpora.utils.format_utils import (
    ANNOTATION_TAG_SEP,
    STANDARTIZATION_REGEX,
    STANDARTIZATION_NUM_REGEX,
    ANNOTATION_NUM_REGEX
)
from corpora.utils.elan_utils import (
    ElanObject,
    get_tier_alignment,
    get_annotation_alignment
)
from corpora.utils.annotation_menu import AnnotationMenu


with open('../data/auxiliary/legacy_manual_anns.json') as f:
    legacy_manual_anns = json.load(f)

grammemes_config_path = 'annotation_grammemes.json'
with open('../data/static/' + grammemes_config_path) as f:
    grammeme_config = json.load(f)

conn = sqlite3.connect('../db_20250111.sqlite3')
c = conn.cursor()

m = pymorphy2.MorphAnalyzer()


def get_recordings():
    recs = c.execute("""
        SELECT data 
        FROM corpora_recording 
        WHERE checked = 1
    """).fetchall()
    return recs


def reverse_tags():
    reverse_compulsory = {v['surface_tag']: v for k, v in grammeme_config['grammemes'].items()}
    assert len(reverse_compulsory) == len(grammeme_config['grammemes'])

    reverse_faculatative = {k: k for k in grammeme_config["facultative"].keys()}
    assert len(reverse_faculatative) == len(grammeme_config["facultative"])

    return reverse_compulsory, reverse_faculatative


def get_correct_rec_path(rec):
    clean_rec = rec[0].rsplit('/', 1)[-1]
    rec_full_path = "../data/media/" + clean_rec
    return clean_rec, rec_full_path


def get_tiers(rec):
    eaf_obj = Eaf(rec)

    for tier_name, tier in eaf_obj.tiers.items():
        standartization_tier_name = STANDARTIZATION_REGEX.search(tier_name)
        if standartization_tier_name is None:
            continue

        speaker_tier = standartization_tier_name.group(1)
        try:
            orig_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker_tier), key=lambda x: x[0])
            standartization_tier = sorted(eaf_obj.get_annotation_data_for_tier(tier_name), key=lambda x: x[0])
            annotation_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker_tier + '_annotation'), key=lambda x: x[0])
        except KeyError:
            print('ERROR: ' + rec + ': lacking tiers for ' + speaker_tier)
            continue

        yield speaker_tier, orig_tier, standartization_tier, annotation_tier


def get_annotations(orig_tier, standartization_tier, annotation_tier):
    tier_alignment = get_tier_alignment(orig_tier, standartization_tier, annotation_tier)
    for (start, end), (orig, standartization, annotation) in tier_alignment.items():
        standartizations = get_annotation_alignment(standartization, num_regex=STANDARTIZATION_NUM_REGEX)
        annotations = get_annotation_alignment(annotation, num_regex=ANNOTATION_NUM_REGEX)
        yield start, end, standartizations, annotations


def hyphens_to_dots(word):
    return re.sub(r"-(V|Cmp|Af)-", r"-\1.", word)


def get_tag_value_from_obj(tag, key):
    try:
        return getattr(tag, key) or ""
    except AttributeError:
        return ""


def parse_anns_from_annotation(standartizations, annotations):
    anns = []

    if not annotations or not standartizations:
        return anns

    max_idx = max(
        max(annotations.keys()),
        max(standartizations.keys())
    )

    for i in range(max_idx + 1):
        if i not in standartizations:
            anns.append(("", "", ""))
            continue

        std = standartizations[i]
        if i not in annotations:
            anns.append((std, "", ""))
            continue

        lemma, raw_ann = annotations[i]

        if raw_ann == 'длуg-NOUN-m-gen-sg-inan':
            anns.append((std, lemma, 'NOUN-m-gen-sg-inan'))
            continue

        fixed = hyphens_to_dots(raw_ann)
        ann = re.search(r"[а-яёА-ЯЁ ]-([^а-яёА-ЯЁ ]+)", fixed).group(1)
        anns.append((std, lemma, ann))

    return anns


def process_tags_from_one_tier(all_tags, orig_tier, standartization_tier, annotation_tier):
    anns = []
    for _, _, standartizations, annotations in get_annotations(orig_tier, standartization_tier, annotation_tier):
        anns.extend(parse_anns_from_annotation(standartizations, annotations))

    for std, lemma, ann in anns:
        for tag in ann.split(ANNOTATION_TAG_SEP):
            all_tags[tag].append((std + ':' + lemma + ':' + ann))

    return all_tags


def get_tags_by_recording(rec):
    all_tags = defaultdict(list)
    for _, orig_tier, standartization_tier, annotation_tier in get_tiers(rec):
        all_tags = process_tags_from_one_tier(all_tags, orig_tier, standartization_tier, annotation_tier)
    return all_tags


def infer_missing_tag(missing_tag, reverse_tag_list, std, lemma):
    parsed = m.parse(std)
    for p in parsed:
        if not p.normal_form == lemma:
            continue

        if not all(tag in p.tag for tag in reverse_tag_list):
            continue

        missing_tag = get_tag_value_from_obj(p.tag, missing_tag)
        if missing_tag:
            return missing_tag

    return ""


def order_compulsory_tags(rec, menu, reverse_compulsory, pos, tags_dict, tag_list, std, lemma, errors):
    example = [rec, std, lemma, ANNOTATION_TAG_SEP.join(tag_list)]
    final_tags = [pos]

    if pos not in menu.config['order']:
        return final_tags, errors

    order = menu.get_order_by_tag(pos, tags_dict)
    order_tags = {k.strip('*') for k in order}  # remove the mark of not-always-required tags

    abundant = {
        k: v
        for k, v in tags_dict.items()
        if k not in order_tags and k != "part of speech"
    }
    needed = {v for k, v in tags_dict.items() if k not in abundant}

    reverse_tag_list = [
        reverse_compulsory[tag]["pymorphy_tag"]
        for tag in tag_list
        if tag in reverse_compulsory
        and tag in needed
    ]

    for key in order:
        key_always_required = True
        if key.startswith('*'):
            key_always_required = False
            key = key[1:]

        if key not in tags_dict:
            missing_tag = infer_missing_tag(key, reverse_tag_list, std, lemma)
            surface_tag = menu.config['grammemes'].get(missing_tag, {}).get("surface_tag", "")
            if surface_tag:
                final_tags.append(surface_tag)
            elif key_always_required:
                errors['no ' + key + ' for ' + pos].append(example)
                final_tags.append('')
            continue

        final_tags.append(tags_dict[key])

    if abundant:
        errors['abundant_tags'].append(example + [ANNOTATION_TAG_SEP.join(final_tags), abundant])

    return final_tags, errors


def fix_legacy_tags(tags):
    fixed_tags = []

    for tag in tags:
        if tag not in legacy_manual_anns:
            fixed_tags.append(tag)
            continue

        elif legacy_manual_anns[tag][1] is None:
            continue

        else:
            fixed_tags.append(legacy_manual_anns[tag][1])

    return fixed_tags


def fix_legacy_tag_combinations(word, tags):
    if 'ADV' in tags and 'dmns' in tags:
        tags.append('Apro')

    if 'ADV' in tags and 'Q' in tags and word in {'где', 'зачем', 'откуда', 'почему'}:
        tags.append('Apro')
        tags[tags.index('Q')] = 'WH'

    if word == "это" and "PA" in tags:
        tags = "NPRO-n-nom-sg".split("-")

    if word in ['я', 'ты', 'мы', 'вы']:
        tags = [t for t in tags if t not in ['f', 'm', 'n', 'mf']]

    return tags


def reorder_tags_for_word(rec, tags, std, lemma, annotation_menu, errors):
    reverse_compulsory, all_facultative = reverse_tags()
    compulsory_tags_dict = {}
    tags = fix_legacy_tags(tags)
    tags = fix_legacy_tag_combinations(lemma, tags)

    for tag in tags:
        if tag in reverse_compulsory:
            compulsory_tags_dict[reverse_compulsory[tag]['category']] = tag

    pos = compulsory_tags_dict.get('part of speech')
    if pos is None:  # UNKN, LATIN, PNCT
        errors['no pos'].append([rec, std, lemma, ANNOTATION_TAG_SEP.join(tags)])
        return tags, errors
    final_tags, errors = order_compulsory_tags(
        rec, annotation_menu, reverse_compulsory, pos,
        compulsory_tags_dict, tags, std, lemma, errors
    )
    raw_facultative = [t for t in tags if t in all_facultative]
    facultative = annotation_menu.order_facultative_tags(raw_facultative, final_tags, std)
    final_tags += facultative

    return final_tags, errors


def reorder_tags_for_recs(annotation_menu, recs):
    errors = defaultdict(list)

    for rec in recs:
        clean_rec, rec_full_path = get_correct_rec_path(rec)
        elan_obj = ElanObject(rec_full_path)

        tier_names, starts, ends, all_anns = [], [], [], []
        print(clean_rec)

        for speaker_tier_name, orig_tier, standartization_tier, annotation_tier in get_tiers(rec_full_path):
            for start, end, standartizations, annotations in get_annotations(orig_tier, standartization_tier, annotation_tier):
                anns = parse_anns_from_annotation(standartizations, annotations)
                new_anns = []
                for token in anns:
                    std, lemma, token_ann = token
                    tags = token_ann.split(ANNOTATION_TAG_SEP)
                    final_tags, errors = reorder_tags_for_word(
                        clean_rec, tags, std, lemma, annotation_menu, errors
                    )
                    new_anns.append((std, [(lemma, ANNOTATION_TAG_SEP.join(final_tags))]))

                tier_names.append(speaker_tier_name)
                starts.append(start)
                ends.append(end)
                all_anns.append(new_anns)

        elan_obj.update_anns(tier_names, starts, ends, all_anns)
        elan_obj.save()

    # print_errors(errors)


def get_undefined_tags(recs):
    compulsory, facultative = reverse_tags()
    not_present = defaultdict(lambda: [[], []])

    for rec in recs:
        clean_rec, rec_full_path = get_correct_rec_path(rec)
        rec_tags = get_tags_by_recording(rec_full_path)
        for tag, examples in rec_tags.items():
            if tag and tag not in compulsory and tag not in facultative:
                not_present[tag][0].append(clean_rec)
                not_present[tag][1].extend(examples[:3])

    not_present_template = {k: ["", "", v[1][:3]] for k, v in sorted(not_present.items())}
    for k, v in not_present_template.items():
        print(k + ';' + ', '.join(v[2]))


def print_errors(errors):
    for k, vs in errors.items():
        print(k)
        print(str(len(vs)) + ' ' + ', '.join('|'.join(str(x) for x in tag) for tag in vs[:3]))
        print('=' * 20)

    print('\nAbundant')
    abundant_tags_groups = defaultdict(list)
    for item in errors['abundant_tags']:
        tags = ','.join(sorted(item[-1].keys()))
        abundant_tags_groups[tags].append(item)
    for group, items in abundant_tags_groups.items():
        print(group, len(items), ', '.join('|'.join(item[:-1]) for item in items[:4]), sep=';')
    print('+' * 30 + '\n')

    with open('local_abundant_gender.csv', 'w') as f:
        lines = '\n'.join(';'.join(item[:-1]) for item in abundant_tags_groups['gender'])
        f.write(lines)

    with open('local_no_animacy.csv', 'w') as f:
        lines = "\n".join(
            ";".join(['no animacy for NOUN', rec, std, lemma, tags])
            for rec, std, lemma, tags in errors["no animacy for NOUN"]
        )
        f.write(lines)

    no_aspect_for_verb = errors['no aspect for VERB']
    print('prf in no aspect for VERB', sum('prf' in tags[2].split(ANNOTATION_TAG_SEP) for tags in no_aspect_for_verb))
    print('Other')
    for ann in no_aspect_for_verb:
        rec, std, lemma, tags = ann
        if 'prf' not in tags.split(ANNOTATION_TAG_SEP):
            print('no aspect for VERB', rec, std, lemma, tags, sep=";")
    print('+' * 30 + '\n')

    no_pos = errors['no pos']
    print('no pos', Counter(tags[2].split(ANNOTATION_TAG_SEP)[0] for tags in no_pos))
    print('Other')
    for ann in no_pos:
        rec, std, lemma, tags = ann
        if 'INFN' not in tags.split(ANNOTATION_TAG_SEP):
            print('no pos', rec, std, lemma, tags, sep=";")
    print('+' * 30 + '\n')

    no_gender_for_noun = errors['no gender for NOUN']
    print(
        'GNdr or Ms in no gender for NOUN',
        sum('GNdr' in tags[2].split(ANNOTATION_TAG_SEP) or 'Ms' in tags[2].split(ANNOTATION_TAG_SEP) for tags in no_gender_for_noun)
    )
    print('Other')
    for ann in no_gender_for_noun:
        rec, std, lemma, tags = ann
        if not('GNdr' in tags.split(ANNOTATION_TAG_SEP) or 'Ms' in tags.split(ANNOTATION_TAG_SEP)):
            print('no gender for NOUN', rec, std, lemma, tags, sep=";")
    print('+' * 30 + '\n')

    no_number_for_noun = errors['no number for NOUN']
    print(
        'Pltm / Sgtm in no number for NOUN',
        sum('Pltm' in tags[2].split(ANNOTATION_TAG_SEP) or 'Sgtm' in tags[2].split(ANNOTATION_TAG_SEP) for tags in no_number_for_noun)
    )
    print('Other')
    for ann in no_number_for_noun:
        rec, std, lemma, tags = ann
        if not('Pltm' in tags.split(ANNOTATION_TAG_SEP) or 'Sgtm' in tags.split(ANNOTATION_TAG_SEP)):
            print('no number for NOUN', rec, std, lemma, tags, sep=";")
    print('+' * 30 + '\n')

    no_person_for_verb = errors['no person for VERB']
    print('Impe in no person for VERB', sum('Impe' in tags[2].split(ANNOTATION_TAG_SEP) for tags in no_person_for_verb))
    print('Other')
    for ann in no_person_for_verb:
        rec, std, lemma, tags = ann
        if 'Impe' not in tags.split(ANNOTATION_TAG_SEP):
            print('no person for VERB', rec, std, lemma, tags, sep=";")
    print('+' * 30 + '\n')

    no_voice_for_prts = errors['no voice for PRTS']
    print('pssv in no voice for PRTS', sum('pssv' in tags[2].split(ANNOTATION_TAG_SEP) for tags in no_voice_for_prts))


if __name__ == '__main__':
    annotation_menu = AnnotationMenu(grammemes_config_path)
    recs = get_recordings()

    # get_undefined_tags(recs)
    reorder_tags_for_recs(annotation_menu, recs)