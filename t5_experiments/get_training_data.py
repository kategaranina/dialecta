import os
import json

from pympi import Eaf

from corpora.utils.elan_utils import (
    clean_transcription, get_tier_alignment,
    get_annotation_alignment
)
from corpora.utils.format_utils import (
    STANDARTIZATION_REGEX, STANDARTIZATION_NUM_REGEX
)


DATA_DIR = '/Users/kategerasimenko/Desktop/robota/data/dialecta_eafs/bel_checked'
SKIPPED_TOK = '<skipped>'

annot_pairs = []

for recname in os.listdir(DATA_DIR):
    if not recname.endswith('.eaf'):
        continue

    print(recname)

    eaf_obj = Eaf(os.path.join(DATA_DIR, recname))

    # from corpora/utils/word_list.py
    for tier_name, tier in eaf_obj.tiers.items():
        standartization_tier_name = STANDARTIZATION_REGEX.search(tier_name)
        if standartization_tier_name is None:
            continue

        speaker = standartization_tier_name.group(1)
        print(speaker)

        try:
            orig_tier = sorted(eaf_obj.get_annotation_data_for_tier(speaker), key=lambda x: x[0])
            standartization_tier = sorted(eaf_obj.get_annotation_data_for_tier(tier_name), key=lambda x: x[0])
            print(len(orig_tier), len(standartization_tier))

            tier_alignment = get_tier_alignment(orig_tier, standartization_tier, annotation_tier=None)

            for orig, standartization, annotation in tier_alignment.values():
                standartizations = get_annotation_alignment(standartization, num_regex=STANDARTIZATION_NUM_REGEX)
                orig_words = clean_transcription(orig).split()
                std = [standartizations.get(i, SKIPPED_TOK) for i in range(len(orig_words))]

                annot_pairs.append({
                    'recording': recname,
                    'speaker': speaker,
                    'input': ' | '.join(orig_words),
                    'output': ' | '.join(std)
                })

        except Exception as e:
            print(recname, tier_name, e)

    a = 5

with open('annotation_data.json', 'w') as f:
    json.dump(annot_pairs, f, ensure_ascii=False, indent=2)
