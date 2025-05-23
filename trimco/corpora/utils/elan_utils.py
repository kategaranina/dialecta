import os
from decimal import Decimal
from pympi import Eaf, Elan
from .format_utils import (
    TECH_REGEX, ANNOTATION_WORD_SEP, ANNOTATION_PART_SEP,
    ANNOTATION_TAG_SEP, UNKNOWN_PREFIX
)


# TODO: join all funcs in ElanObject and use it everywhere


class Tier:
    def __init__(self, name, info):
        self.name = name
        self.aligned_annotations = info[0]
        self.reference_annotations = info[1]
        self.attributes = info[2]
        self.ordinal = info[3]

        self.top_level = False
        if 'PARENT_REF' not in self.attributes.keys():
            self.top_level = True

        self.side = None
        if '_i_' in self.name:
            self.side = 'interviewer'
        elif '_n_' in self.name:
            self.side = 'speaker'


class ElanObject:
    def __init__(self, path_to_file):
        self.path = path_to_file
        self.Eaf = Eaf(path_to_file)
        self.Eaf.clean_time_slots()
        self.load_tiers()
        self.load_annotation_data()
        self.load_participants()

    def load_participants(self):
        participants_lst = []

        for tier_obj in self.tiers_lst:
            try:
                p_title = tier_obj.attributes['PARTICIPANT'].title()
                if p_title not in participants_lst:
                    participants_lst.append(p_title)
            except KeyError:
                pass

        self.participants_lst = participants_lst

    def load_tiers(self):
        tiers_lst = []
        for tier_name, tier_info in self.Eaf.tiers.items():
            tiers_lst.append(Tier(tier_name, tier_info))
        self.tiers_lst = sorted(tiers_lst, key=lambda data: data.ordinal)

    def load_annotation_data(self):
        annot_data_lst = []
        for tier_obj in self.tiers_lst:
            if tier_obj.top_level:
                for annot_data in self.Eaf.get_annotation_data_for_tier(tier_obj.name):
                    annot_data_lst.append(annot_data + (tier_obj.name,))
        self.annot_data_lst = sorted(annot_data_lst, key=lambda data: data[0])

    def get_tier_obj_by_name(self, tier_name):
        for tier_obj in self.tiers_lst:
            if tier_obj.name == tier_name:
                return tier_obj
        return None

    def add_extra_tags(self, parent_tier_name, start, end, value, typ):
        if typ == 'annotation':
            tier_name = parent_tier_name + '_annotation'
            ling = 'tokenz_and_annot'
        elif typ == 'standartization':
            tier_name = parent_tier_name + '_standartization'
            ling = 'stndz_clause'
        else:
            return

        if self.get_tier_obj_by_name(tier_name) is None:
            self.Eaf.add_tier(tier_name, ling=ling, parent=parent_tier_name)
            self.load_tiers()

        try:
            self.Eaf.remove_annotation(tier_name, (start + end) / 2, clean=True)
        except KeyError:
            pass

        self.Eaf.add_annotation(tier_name, start, end, value)

    def save(self):
        self.Eaf.clean_time_slots()
        try:
            os.remove(self.path + '.bak')
        except OSError:
            pass

        Elan.to_eaf(self.path, self.Eaf, pretty=True)
        os.remove(self.path + '.bak')

    def _update_ann(self, tier_name, start, end, annot_value_lst, nrm_value_lst):
        if annot_value_lst:
            self.add_extra_tags(
                tier_name, start, end, ANNOTATION_WORD_SEP.join(annot_value_lst), 'annotation'
            )
        if nrm_value_lst:
            self.add_extra_tags(
                tier_name, start, end, ANNOTATION_WORD_SEP.join(nrm_value_lst), 'standartization'
            )

    def process_html_annot(self, html_annot):
        tier_name = html_annot.xpath('*[@class="annot"]/@tier_name')[0]
        raw_start = html_annot.xpath('*[@class="audiofragment"]/@starttime')[0]
        raw_end = html_annot.xpath('*[@class="audiofragment"]/@endtime')[0]
        start = int(Decimal(raw_start))
        end = int(Decimal(raw_end))
        t_counter = 0
        annot_value_lst = []
        nrm_value_lst = []

        for token in html_annot.xpath('*//token'):
            nrm_lst = token.xpath('nrm/text()')
            lemma_lst = token.xpath('lemma/text()')
            morph_lst = token.xpath('morph/text()')

            try:
                if lemma_lst + morph_lst:
                    annot_value_lst.append(ANNOTATION_PART_SEP.join([str(t_counter), lemma_lst[0], morph_lst[0]]))
                if nrm_lst:
                    nrm_value_lst.append(ANNOTATION_PART_SEP.join([str(t_counter), nrm_lst[0]]))
            except IndexError:
                print(
                    'Exception while saving. Normalization: %s,'
                    'Lemmata: %s, Morphology: %s, Counter: %s'
                    % (nrm_lst, lemma_lst, morph_lst, t_counter)
                )

            t_counter += 1

        self._update_ann(tier_name, start, end, annot_value_lst, nrm_value_lst)

    def update_anns(self, tier_names, starts, ends, annotations):
        for tier_name, start, end, annotation in zip(tier_names, starts, ends, annotations):
            annot_value_lst = []
            nrm_value_lst = []
            for t_counter, token in enumerate(annotation):
                nrm = token[0]
                anns = token[1]
                lemma = anns[0][0] if anns else ''
                morph = anns[0][1] if anns else ''
                try:
                    if lemma + morph:
                        annot_value_lst.append(ANNOTATION_PART_SEP.join([str(t_counter), lemma, morph]))
                    if nrm:
                        nrm_value_lst.append(ANNOTATION_PART_SEP.join([str(t_counter), nrm]))
                except IndexError:
                    print(
                        'Exception while saving. Normalization: %s,'
                        'Lemmata: %s, Morphology: %s, Counter: %s' % (nrm, lemma, morph, t_counter)
                    )

            self._update_ann(tier_name, start, end, annot_value_lst, nrm_value_lst)


def clean_transcription(transcription):
    return TECH_REGEX.sub('', transcription).strip()


def get_tier_alignment(orig_tier, standartization_tier, annotation_tier):
    tier_alignment = {(ann[0], ann[1]): [ann[2], None, None] for ann in orig_tier}

    for ann in standartization_tier:
        if (ann[0], ann[1]) in tier_alignment:
            tier_alignment[(ann[0], ann[1])][1] = ann[2]

    for ann in annotation_tier:
        if (ann[0], ann[1]) in tier_alignment:
            tier_alignment[(ann[0], ann[1])][2] = ann[2]

    return tier_alignment


def get_annotation_alignment(annotation, num_regex):
    annotations = {}
    if annotation is not None:
        for ann in annotation.split(ANNOTATION_WORD_SEP):
            ann_parts = num_regex.search(ann).groups()
            ann_num = ann_parts[0]
            # ann_parts len is 3 for annotations and 2 for standartizations
            ann = ann_parts[1:] if len(ann_parts) > 2 else ann_parts[1]
            annotations[int(ann_num)] = ann
    return annotations


def split_ann_for_db(ann):
    lemma_view, tags_view = ann  # should always be a list
    lemma = lemma_view.lower().replace(UNKNOWN_PREFIX, '')
    tags = tags_view.lower().split(ANNOTATION_TAG_SEP)
    annotation = {
        'lemma': lemma,
        'tags': tags,
        'lemma_view': lemma_view,
        'tags_view': tags_view
    }

    return annotation
