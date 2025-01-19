import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trimco.settings")

import django
django.setup()

from pathlib import Path

import sqlite3

from corpora.utils.elan_to_html import ElanToHTML
from corpora.utils.elan_utils import clean_transcription, ElanObject
from corpora.utils.standartizator import Standartizator
from corpora.utils.format_utils import ANNOTATION_PART_SEP, ANNOTATION_WORD_SEP


conn = sqlite3.connect('db_20250111.sqlite3')
c = conn.cursor()

media_dir = 'data/media/all/'


class Annotator(ElanToHTML):
    def __init__(self, elan_path):
        self.elan_obj = ElanObject(elan_path)


def get_recordings_from_db():
    recs = c.execute("""
        SELECT data, to_dialect_id 
        FROM corpora_recording 
        WHERE checked = 0
    """).fetchall()
    return recs


def write_anns(annotator, annotation, tier_name, start, end):
    annot_value_lst = []
    for i, token in enumerate(annotation):
        nrm = token[0]
        anns = token[1]
        lemma = anns[0][0] if anns else ''
        morph = anns[0][1] if anns else ''
        try:
            if lemma + morph:
                annot_value_lst.append(ANNOTATION_PART_SEP.join([i, lemma, morph]))
        except IndexError:
            print(
                'Exception while saving. Normalization: %s,'
                'Lemmata: %s, Morphology: %s, Counter: %s' % (nrm, lemma, morph, i)
            )

    if annot_value_lst:
        annotator.elan_obj.add_extra_tags(
            tier_name, start, end, ANNOTATION_WORD_SEP.join(annot_value_lst), 'annotation'
        )


def reannotate_grammar_in_rec(annotator, standartizator):
    for annot_data in annotator.elan_obj.annot_data_lst:
        start, end = annot_data[0], annot_data[1]
        tier_name = annot_data[3]

        tier_obj = annotator.elan_obj.get_tier_obj_by_name(tier_name)
        if tier_obj.attributes['TIER_ID'] == 'comment':
            continue

        transcript = clean_transcription(annot_data[2].strip()).split()
        if not transcript:
            continue

        normz_tokens_dict = annotator.get_additional_tags_dict(tier_name + '_standartization', annot_data[0], annot_data[1])
        normz_sorted = sorted(normz_tokens_dict.items(), key=lambda x: x[0])
        nrm_list = [(transcript[i], nrm) for i, nrm in normz_sorted]
        annotation = standartizator.get_grammar_annotation([nrm_list])[0]

        write_anns(annotator, annotation, tier_name, start, end)


def reannotate_rec(rec, to_dialect):
    full_rec_path = Path(Path().resolve(), media_dir, rec)
    annotator = Annotator(full_rec_path)
    standartizator = Standartizator(to_dialect)
    reannotate_grammar_in_rec(annotator, standartizator)


if __name__ == '__main__':
    recs = get_recordings_from_db()
    for rec, to_dialect in recs:
        print('reannotating', rec)
        reannotate_rec(rec, to_dialect)
