import os
import sys
import json
from collections import defaultdict

from pympi import Eaf

sys.path.append('../trimco')
from corpora.utils.elan_utils import (
    clean_transcription, get_tier_alignment,
    get_annotation_alignment
)
from corpora.utils.format_utils import (
    STANDARTIZATION_REGEX, STANDARTIZATION_NUM_REGEX
)


DATA_DIRS = {
    'train': os.path.join('data', 'train'),
    'test': os.path.join('data', 'all')
}

SKIPPED_TOK = '<skipped>'


def get_pairs_from_tier(eaf_obj, split, recname, tier_name, speaker):
    annot_pairs = []

    orig_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker), key=lambda x: x[0])
    standartization_tier = sorted(eaf_obj.get_annotation_data_for_tier(tier_name), key=lambda x: x[0])
    if len(orig_tier) != len(standartization_tier):
        print(speaker, f'Mismatch in orig and standartized: {len(orig_tier)} vs {len(standartization_tier)}')

    tier_alignment = get_tier_alignment(orig_tier, standartization_tier, annotation_tier=None)

    for orig, standartization, annotation in tier_alignment.values():
        if standartization is None:
            continue

        standartizations = get_annotation_alignment(standartization, num_regex=STANDARTIZATION_NUM_REGEX)
        orig_words = clean_transcription(orig).split()
        std = [standartizations.get(i, SKIPPED_TOK) for i in range(len(orig_words))]

        if split == 'train':  # omitting words without normalization
            orig_words = [w for i, w in enumerate(orig_words) if i in standartizations]
            std = [standartizations[i] for i in range(len(orig_words)) if i in standartizations]
            output_key = 'output'
        else:
            output_key = 'old_output'

        if orig_words:
            annot_pairs.append({
                'recording': recname,
                'speaker': speaker,
                'input': ' | '.join(orig_words),
                output_key: ' | '.join(std)
            })

    return annot_pairs


def process_rec(data_dir, split, recname):
    annot_pairs = []

    eaf_obj = Eaf(os.path.join(data_dir, recname))

    # from corpora/utils/word_list.py
    for tier_name, tier in eaf_obj.tiers.items():
        standartization_tier_name = STANDARTIZATION_REGEX.search(tier_name)
        if standartization_tier_name is None:
            continue

        speaker = standartization_tier_name.group(1)

        try:
            tier_annot_pairs = get_pairs_from_tier(eaf_obj, split, recname, tier_name, speaker)
            annot_pairs.extend(tier_annot_pairs)
        except Exception as e:
            print(recname, tier_name, e)

    return annot_pairs


if __name__ == '__main__':
    annot_pairs_by_split = defaultdict(list)

    for part, data_dir in DATA_DIRS.items():
        for recname in os.listdir(data_dir):
            if not recname.endswith('.eaf'):
                continue

            print(recname)
            rec_annot_pairs = process_rec(data_dir, recname=recname, split=part)
            annot_pairs_by_split[part].extend(rec_annot_pairs)

    train_recs = set(os.listdir(DATA_DIRS['train']))
    annot_pairs_by_split['test'] = [
        v for v in annot_pairs_by_split['test']
        if v['recording'] not in train_recs and not v['recording'].startswith('RuPS')  # only Belarusian dialects for now
    ]

    with open('annotation_data.json', 'w') as f:
        json.dump(annot_pairs_by_split, f, ensure_ascii=False, indent=2)
