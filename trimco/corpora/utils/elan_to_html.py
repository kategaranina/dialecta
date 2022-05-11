import datetime
import os
from lxml import etree
from django.conf import settings

from .standartizator import Standartizator
from .elan_utils import ElanObject, clean_transcription
from .format_utils import (
    ANNOTATION_WORD_SEP, ANNOTATION_OPTION_SEP,
    ANNOTATION_TAG_SEP, ANNOTATION_PART_SEP,
    get_audio_link, get_audio_annot_div,
    get_annot_div, get_participant_tag_and_status
)


class ElanToHTML:
    def __init__(self, file_obj, mode='', _format=''):
        self.file_obj = file_obj  # file_obj is a Recording
        self.elan_obj = ElanObject(self.file_obj.data.path)
        self.audio_file_path = self.file_obj.audio.name
        self.path = self.file_obj.data.path
        self.format = _format
        self.mode = mode
        self.dialect = self.file_obj.to_dialect  # gets 'Dialect' field of recording

    def build_page(self):
        if self.mode == 'auto-annotation':
            # before building html, auto-annotation of the whole elan is performed
            self.make_backup()
            self.reannotate_elan()
            # change 'auto_annotated' status of recording to True after performing automatic annotation
            self.change_status_and_save()

        self.build_html()

    def make_backup(self):
        print('Creating backup of current annotation')
        now = datetime.datetime.now()
        cur = now.strftime("%Y-%m-%d_%H%M")
        new_file = '{}_backup_{}.eaf'.format(str(self.path).split('/')[-1][:-4], cur)
        os.system('mkdir -p {}/backups'.format(settings.MEDIA_ROOT))
        os.system('cp {} {}/backups/{}'.format(self.path, settings.MEDIA_ROOT, new_file))

    def change_status_and_save(self):
        self.file_obj.auto_annotated = True
        self.file_obj.save()

    def reannotate_elan(self):
        standartizator = Standartizator(self.dialect)

        tier_names = []
        starts = []
        ends = []
        transcripts = []

        for annot_data in self.elan_obj.annot_data_lst:
            tier_name = annot_data[3]
            tier_obj = self.elan_obj.get_tier_obj_by_name(tier_name)
            if tier_obj.attributes['TIER_ID'] != 'comment':
                start, end, transcript = annot_data[0], annot_data[1], clean_transcription(annot_data[2].strip())
                tier_names.append(tier_name)
                starts.append(start)
                ends.append(end)
                transcripts.append(transcript)

        transcript = '\n'.join(transcripts)
        annotations = standartizator.get_annotation(transcript)

        for tier_name, start, end, transcript, annotation in zip(tier_names, starts, ends, transcripts, annotations):
            t_counter = 0
            annot_value_lst = []
            nrm_value_lst = []
            for token in annotation:
                nrm = token[0]
                anns = token[1]
                lemma = ANNOTATION_OPTION_SEP.join(set([x[0] for x in anns]))
                morph = ANNOTATION_OPTION_SEP.join([x[0] + ANNOTATION_TAG_SEP + x[1] for x in anns])
                try:
                    if lemma + morph:
                        annot_value_lst.append(
                            '%s%s%s%s%s' % (t_counter, ANNOTATION_PART_SEP, lemma, ANNOTATION_PART_SEP, morph)
                        )
                    if nrm:
                        nrm_value_lst.append('%s%s%s' % (t_counter, ANNOTATION_PART_SEP, nrm))
                except IndexError:
                    print(
                        'Exception while saving. Normalization: %s,'
                        'Lemmata: %s, Morphology: %s, Counter: %s' % (nrm, lemma, morph, t_counter)
                    )
                t_counter += 1

            # TODO: copypaste from elan_utils:135
            if annot_value_lst:
                self.elan_obj.add_extra_tags(
                    tier_name, start, end, ANNOTATION_WORD_SEP.join(annot_value_lst), 'annotation'
                )
            if nrm_value_lst:
                self.elan_obj.add_extra_tags(
                    tier_name, start, end, ANNOTATION_WORD_SEP.join(nrm_value_lst), 'standartization'
                )

    def build_html(self):
        print('Transcription > Standard learning examples:', self.file_obj.data.path)

        i = 0
        html = get_audio_link(self.audio_file_path)

        for annot_data in self.elan_obj.annot_data_lst:
            tier_name = annot_data[3]
            tier_obj = self.elan_obj.get_tier_obj_by_name(tier_name)
            tier_id = tier_obj.attributes['TIER_ID']
            if tier_id == 'comment':
                continue

            transcript = annot_data[2]
            if not transcript:
                continue

            normz_tokens_dict = self.get_additional_tags_dict(tier_name+'_standartization', annot_data[0], annot_data[1])
            annot_tokens_dict = self.get_additional_tags_dict(tier_name+'_annotation', annot_data[0], annot_data[1])
            participant, tier_status = get_participant_tag_and_status(tier_obj.attributes['PARTICIPANT'], tier_id)
            audio_div = get_audio_annot_div(annot_data[0], annot_data[1])
            annot_div = get_annot_div(
                tier_name, self.dialect.id, participant, transcript, normz_tokens_dict, annot_tokens_dict,
                elan_file=str(self.path).rsplit('/', 1)[-1]
            )
            html += '<div class="annot_wrapper %s">%s%s</div>' % (tier_status, audio_div, annot_div)
            i += 1

        self.html = '<div class="eaf_display">%s</div>' %(html)

    def collect_examples(self):
        """
        collects pairs <transcribed sentence> - <normalized sentence> from elan-file
        it's needed to retrain normalization models
        returns list of ('transcription', 'normalization')
        """
        examples = []

        for annot_data in self.elan_obj.annot_data_lst:
            tier_name = annot_data[3]
            tier_obj = self.elan_obj.get_tier_obj_by_name(tier_name)
            if tier_obj.attributes['TIER_ID'] != 'comment':
                transcription = annot_data[2]
                normz_tokens_dict = self.get_additional_tags_dict(tier_name+'_standartization', annot_data[0], annot_data[1])
                normz_sorted = sorted(normz_tokens_dict.items())
                normalization = ' '.join(item[1][0] for item in normz_sorted)
                examples.append((transcription, normalization))

        return examples
        
    def get_additional_tags_dict(self, tier_name, start, end):
        tokens_dict = {}

        try:
            nrm_annot_lst = self.elan_obj.Eaf.get_annotation_data_at_time(tier_name, (start+end) / 2)
            if not nrm_annot_lst:
                return tokens_dict

            nrm_annot = nrm_annot_lst[0][-1].split(ANNOTATION_WORD_SEP)
            for el in nrm_annot:
                el = el.split(ANNOTATION_PART_SEP)
                tokens_dict[int(el[0])] = el[1:]

        except KeyError:
            pass

        return tokens_dict

    def save_html_to_elan(self, html):
        html_obj = etree.fromstring(html)
        for el in html_obj.xpath('//*[contains(@class,"annot_wrapper")]'):
            self.elan_obj.process_html_annot(el)
        self.elan_obj.save()

    @staticmethod
    def save_html_extracts_to_elans(html):
        html_obj = etree.fromstring(html)
        for el in html_obj.xpath('//*[contains(@class, "annot_wrapper") and contains(@class, "changed")]'):
            elan_name = el.xpath('*[@class="annot"]/@elan')[0]
            elan_obj = ElanObject(os.path.join(settings.MEDIA_ROOT, elan_name))
            elan_obj.process_html_annot(el)
            elan_obj.save()
