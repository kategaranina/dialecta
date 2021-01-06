import datetime
import re
from pympi import Eaf, Elan
from lxml import etree
from decimal import *
from corpora.models import *
from .misc import clean_transcription
from .annotation_menu import AnnotationMenuFromXML
from .standartizator import Standartizator


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
        for tier_name in self.Eaf.tiers.keys():
            tiers_lst.append(Tier(tier_name, self.Eaf.tiers[tier_name]))
        self.tiers_lst = sorted(tiers_lst, key=lambda data: data.ordinal)
        
    def load_annotation_data(self):
        annot_data_lst = []
        for tier_obj in self.tiers_lst:
            if tier_obj.top_level:
                for annot_data in self.Eaf.get_annotation_data_for_tier(tier_obj.name):
                    annot_data_lst.append(annot_data+(tier_obj.name,))
        self.annot_data_lst = sorted(annot_data_lst, key=lambda data: data[0])

    def get_tier_obj_by_name(self, tier_name):
        for tier_obj in self.tiers_lst:
            if tier_obj.name == tier_name:
                return tier_obj
        return None
    
    def add_extra_tags(self, parent_tier_name, start, end, value, typ):
        if typ == 'annotation':
            tier_name = parent_tier_name+'_annotation'
            ling = 'tokenz_and_annot'
        elif typ == 'standartization':
            tier_name = parent_tier_name+'_standartization'
            ling = 'stndz_clause'
        else:
            return

        if self.get_tier_obj_by_name(tier_name) is None:
            self.Eaf.add_tier(tier_name, ling=ling, parent=parent_tier_name)
            self.load_tiers()

        try:
            self.Eaf.remove_annotation(tier_name, (start+end) / 2, clean=True)
        except KeyError:
            pass

        self.Eaf.add_annotation(tier_name, start, end, value)
    
    def save(self):
        self.Eaf.clean_time_slots()
        try:
            os.remove(self.path+'.bak')
        except OSError:
            pass

        Elan.to_eaf(self.path, self.Eaf, pretty=True)
        os.remove(self.path+'.bak')


class ElanToHTML:
    def __init__(self, file_obj, mode='', _format=''):
        self.file_obj = file_obj  # file_obj is a Recording
        self.elan_obj = ElanObject(self.file_obj.data.path)
        self.audio_file_path = self.file_obj.audio.name
        self.path = self.file_obj.data.path
        self.format = _format
        self.annotation_menu = AnnotationMenuFromXML("grammemes_pymorphy2.xml")
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
                lemma = '/'.join(set([x[0] for x in anns]))
                morph = '/'.join([x[0] + '-' + x[1] for x in anns])
                try:
                    if lemma + morph:
                        annot_value_lst.append('%s:%s:%s' % (t_counter, lemma, morph))
                    if nrm:
                        nrm_value_lst.append('%s:%s' % (t_counter, nrm))
                except IndexError:
                    print(
                        'Exception while saving. Normalization: %s,'
                        'Lemmata: %s, Morphology: %s, Counter: %s' % (nrm, lemma, morph, t_counter)
                    )
                t_counter += 1

            if annot_value_lst:
                self.elan_obj.add_extra_tags(tier_name, start, end, '|'.join(annot_value_lst), 'annotation')
            if nrm_value_lst:
                self.elan_obj.add_extra_tags(tier_name, start, end, '|'.join(nrm_value_lst), 'standartization')

    def build_html(self):
        print('Transcription > Standard learning examples:', self.file_obj.data.path)

        i = 0
        self.participants_dict = {}
        html = self.get_audio_link()

        for annot_data in self.elan_obj.annot_data_lst:
            tier_name = annot_data[3]
            tier_obj = self.elan_obj.get_tier_obj_by_name(tier_name)
            if tier_obj.attributes['TIER_ID'] != 'comment':
                transcript = annot_data[2]
                if transcript:
                    normz_tokens_dict = self.get_additional_tags_dict(tier_name+'_standartization', annot_data[0], annot_data[1])
                    annot_tokens_dict = self.get_additional_tags_dict(tier_name+'_annotation', annot_data[0], annot_data[1])
                    participant, tier_status = self.get_participant_tag_and_status(tier_obj)
                    audio_div = self.get_audio_annot_div(annot_data[0], annot_data[1])
                    annot_div = self.get_annot_div(tier_name, participant, transcript, normz_tokens_dict, annot_tokens_dict)
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

            nrm_annot = nrm_annot_lst[0][-1].split('|')
            for el in nrm_annot:
                el = el.split(':')
                tokens_dict[int(el[0])] = el[1:]

        except KeyError:
            pass

        return tokens_dict

    def get_participant_tag_and_status(self, tier_obj):
        participant = ''
        tier_status = ''
        if tier_obj is None:
            return participant, tier_status

        participant = tier_obj.attributes['PARTICIPANT'].title()
        if participant not in self.participants_dict:
            filtered_participant = filter(None, participant.split(' '))
            self.participants_dict[participant] = '. '.join(namepart[0] for namepart in filtered_participant) + '.'
        else:
            participant = self.participants_dict[participant]

        if '_i_' in tier_obj.attributes['TIER_ID']:
            tier_status = ' inwr'
        elif '_n_' in tier_obj.attributes['TIER_ID']:
            tier_status = ' inwd'

        return participant, tier_status

    def get_annot_div(self, tier_name, participant, transcript, normz_tokens_dict, annot_tokens_dict):
        transcript = self.prettify_transcript(transcript)
        if annot_tokens_dict:
            transcript = self.add_annotation_to_transcript(transcript, normz_tokens_dict, annot_tokens_dict)
        return '<div class="annot" tier_name="%s"><span class="participant">%s</span><span class="transcript">%s</span></div>' % (tier_name, participant, transcript,)

    @staticmethod
    def get_audio_annot_div(stttime, endtime):
        return '<div class="audiofragment" starttime="%s" endtime="%s"><button class="fa fa-spinner off"></button></div>' %(stttime, endtime)

    def get_audio_link(self):
        return '<audio id="elan_audio" src="/media/%s" preload></audio>' % (self.audio_file_path,)

    @staticmethod
    def prettify_transcript(transcript):
        if not transcript[-1].strip():
            transcript.pop()

        new_transcript = ''
        tokens_lst = re.split('([ ])', transcript)
        
        for el in tokens_lst:
            el = el.strip()
            if not el:
                continue

            if el in ['...', '?', '!']:
                new_el = '<tech>%s</tech>' % el

            elif el[-1] in ['?', '!']:
                new_el = '<token><trt>%s</trt></token><tech>%s</tech>' % (el[:-1], el[-1])

            elif '[' in el and ']' in el:
                new_el = ''

                for el_2 in re.split(r'[\[\]]', el):  # splitting [ ]
                    if not re.match('[a-zA-Z]', el_2):
                        continue  # removing non-alphabetic values

                    if 'unint' in el_2 or '.' in el_2:
                        new_el += '<note>%s.</note>' % el_2.strip('.')
                    else:
                        new_el += '<token><trt>%s</trt></token>' % el_2

            else:
                new_el = '<token><trt>%s</trt></token>' % el

            new_transcript += new_el

        return new_transcript

    def add_annotation_to_transcript(self, transcript, normz_tokens_dict, annot_tokens_dict):
        i = 0
        transcript_obj = etree.fromstring('<c>'+transcript+'</c>')

        for tag in transcript_obj.iterchildren():
            if tag.tag != 'token':
                continue

            if i in annot_tokens_dict.keys():
                morph_tags_full = annot_tokens_dict[i][1].split('/')
                morph_tags_full = '/'.join(
                    self.annotation_menu.override_abbreviations(x, is_lemma=True)
                    for x in morph_tags_full
                )  # DB
                tag.insert(0, etree.fromstring('<morph_full style="display:none">' + morph_tags_full + '</morph_full>'))

                moprh_tags = morph_tags_full[0].split('-', 1)[1]
                morph_tags = self.annotation_menu.override_abbreviations(moprh_tags)  # DB
                tag.insert(0, etree.fromstring('<morph>' + morph_tags + '</morph>'))

                lemma_full = annot_tokens_dict[i][0]
                tag.insert(0, etree.fromstring('<lemma_full style="display:none">' + lemma_full + '</lemma_full>'))

                lemma = lemma_full.split('/')[0]
                tag.insert(0, etree.fromstring('<lemma>' + lemma + '</lemma>'))

            if i in normz_tokens_dict.keys():
                tag.insert(0, etree.fromstring('<nrm>' + normz_tokens_dict[i][0] + '</nrm>'))

            i += 1

        return etree.tostring(transcript_obj)[3:-4].decode('utf-8')

    def save_html_to_elan(self, html):
        html_obj = etree.fromstring(html)

        for el in html_obj.xpath('//*[contains(@class,"annot_wrapper")]'):
            tier_name = el.xpath('*[@class="annot"]/@tier_name')[0]
            raw_start = el.xpath('*[@class="audiofragment"]/@starttime')[0]
            raw_end = el.xpath('*[@class="audiofragment"]/@endtime')[0]
            start = int(Decimal(raw_start))
            end = int(Decimal(raw_end))
            t_counter = 0
            annot_value_lst = []
            nrm_value_lst = []

            for token in el.xpath('*//token'):    
                nrm_lst = token.xpath('nrm/text()')
                lemma_lst = token.xpath('lemma_full/text()')
                morph_lst = token.xpath('morph_full/text()')

                try:
                    if lemma_lst + morph_lst:
                        annot_value_lst.append('%s:%s:%s' % (t_counter, lemma_lst[0], morph_lst[0]))
                    if nrm_lst:
                        nrm_value_lst.append('%s:%s' % (t_counter, nrm_lst[0]))
                except IndexError:
                    print(
                        'Exception while saving. Normalization: %s,'
                        'Lemmata: %s, Morphology: %s, Counter: %s'
                        % (nrm_lst, lemma_lst, morph_lst, t_counter)
                    )

                t_counter += 1

            if annot_value_lst:
                self.elan_obj.add_extra_tags(tier_name, start, end, '|'.join(annot_value_lst), 'annotation')

            if nrm_value_lst:
                self.elan_obj.add_extra_tags(tier_name, start, end, '|'.join(nrm_value_lst), 'standartization')

        self.elan_obj.save()

    def build_annotation_menu(self):
        return [
            self.annotation_menu.menu_html_str_1,
            self.annotation_menu.menu_html_str_2
        ]
