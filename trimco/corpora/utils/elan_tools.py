import pymorphy2
import datetime
import re
import json
from collections import defaultdict, Counter
from pympi import Eaf, Elan
from lxml import etree
from decimal import *
from corpora.models import *
from normalization.models import Model, Word
from .misc import clean_transcription
from .word_list import find_word, find_standartization


class Standartizator:
    def __init__(self, dialect=''):
        self.dialect = dialect

        # gets appropriate model by dialect's name
        # self.model corresponds to the name of model's directory inside csmtiser
        self.model = Model.objects.get(to_dialect=self.dialect)

        self.manual_words = defaultdict(list)
        for x in Word.objects.filter(to_model=self.model):
            self.manual_words[x.transcription].append([x.normalization, x.lemma, x.annotation, 1])

        self.path = settings.NORMALIZER_PATH  # specified in the last line of trimco.settings.py
        self.annotation_menu = AnnotationMenuFromXML("grammemes_pymorphy2.xml")
        self.morph_rus = pymorphy2.MorphAnalyzer()  # TODO: replace with some context-dependent analyser, i.e. mystem

    # TODO: move somewhere else
    def correct_reflexive(self, norm):
        vowels = set('аеёиоуыэюя')
        if len(norm) > 2 and norm[-3] in vowels:
            if len(norm) > 3 and norm[-4] not in vowels: # participles
                new_norm = norm[:-1]+'ь'
                ann = self.morph_rus.parse(new_norm)[0]
                ann_methods = {str(x[0]) for x in ann.methods_stack}
                if ann.tag.POS == 'VERB' or ann_methods != {'<DictionaryAnalyzer>'}:
                    return new_norm
        return norm

    def get_manual_standartizations(self, orig):
        orig = orig.lower()
        manual_standartization = self.manual_words.get(orig)
        if manual_standartization is not None:
            return [manual_standartization[0][0]]

        saved_word = find_word(orig, model=str(self.model))
        if saved_word is not None:
            standartization_counts = Counter(saved_word['standartizations'])
            standartizations_by_freq = [s[0] for s in standartization_counts.most_common()]
            return standartizations_by_freq

    def get_auto_standartization(self, word):
        orig, standartization = word.split('\t')
        manual_standartizations = self.get_manual_standartizations(orig)
        if manual_standartizations is not None:
            standartization = manual_standartizations[0]

        elif standartization.lower().endswith('ся'):
            standartization = self.correct_reflexive(standartization.lower())

        return orig, standartization.lower()

    def normalize(self, text_to_normalize):
        with open(os.path.join(settings.BASE_DIR, 'tmp'), 'w', encoding='utf-8') as f:
            f.write(text_to_normalize)

        os.system('python2 ' + self.path + 'normalise.py ' + os.path.join(settings.BASE_DIR, 'tmp') + ' ' + str(self.model))

        try:
            # clauses are separated by '\n\n', words inside clause are separeted by '\n'
            clauses = open(os.path.join(settings.BASE_DIR, 'tmp.norm'), encoding='utf-8').read().split('\n\n')
            lines = [clause.split('\n') for clause in clauses if clause]
            # an element of lines looks like:
            # ['I\tИ', 'stálo\tстало', 'užó\tужо', "n'a\tне", "óz'erъm\tозером"]

            normalization_list = [
                [self.get_auto_standartization(word) for word in line]
                for line in lines
            ]

            return normalization_list

        except IndexError:
            return

    @staticmethod
    def get_annotation_options_list_from_manual_words(standartization, manual_corr):
        for corr in manual_corr:
            correct_standartization, lemma, tags, transl = corr
            if correct_standartization == standartization:
                result_list = [[lemma, annot.strip(), 1] for annot in tags.split(';')]
                return result_list
        return []

    @staticmethod
    def get_annotaton_options_list_from_db(annots_from_db):
        total_anns = len(annots_from_db)
        unique_anns = Counter(annots_from_db)
        result_list = []

        for full_tag, count in unique_anns.most_common():
            lemma, tag = full_tag.split('-', 1)
            score = count / total_anns
            result_list.append([lemma, tag, score])

        return result_list

    def get_annotation_options_list_by_parsing(self, orig, standartization):
        result_list = []

        for annot in self.morph_rus.parse(standartization):
            if annot.score <= 0.001:
                continue

            tag = self.annotation_menu.override_abbreviations(str(annot.tag))

            # TODO: move somewhere
            if self.model.name == 'be' and (orig.endswith('ṷšy') or orig.endswith('ṷši')) and tag.startswith('GER-'):
                tag = 'ANTP-' + tag[4:]

            # pymorphy2 specific
            methods = {str(x[0]) for x in annot.methods_stack}
            lemma = annot.normal_form if methods == {'<DictionaryAnalyzer>'} else '(unkn)_' + annot.normal_form

            result_list.append([lemma, tag, annot.score])

        return result_list

    def get_annotation_options_list(self, token):
        orig, standartization = token

        manual_corr = self.manual_words.get(orig.lower())
        if manual_corr is not None:
            return self.get_annotation_options_list_from_manual_words(standartization, manual_corr)

        standartization_from_db = find_standartization(standartization, model=str(self.model))
        if standartization_from_db is not None:
            return self.get_annotaton_options_list_from_db(standartization_from_db['annotations'])

        return self.get_annotation_options_list_by_parsing(orig, standartization)

    def get_annotation(self, text):
        annotations = []
        nrm_list = self.normalize(text)
        for nrm in nrm_list:
            annotation = []
            for word in nrm:
                annotation.append((word[1], self.get_annotation_options_list(word)))
            annotations.append(annotation)
        return annotations

    def make_backup(self):
        """
        creates backups of .norm and .orig files (needed to train the model)
        NB: files should has the same name as the model!
        e.g.: rus.norm and rus.orig for rus model
        """
        self.orig = '{}.orig'.format(self.model)
        self.norm = '{}.norm'.format(self.model)
        self.path_to_model = self.path + str(self.model)  # the full path = path_to_normalizer + model_name

        now = datetime.datetime.now()
        cur = now.strftime("%Y-%m-%d_%H%M")
        new_orig = '{}_{}'.format(self.orig, cur)
        new_norm = '{}_{}'.format(self.norm, cur)

        os.system('mkdir -p {}/backups'.format(self.path_to_model))
        os.system('cp {0}/{1} {0}/backups/{2}'.format(self.path_to_model, self.orig, new_orig))
        os.system('cp {0}/{1} {0}/backups/{2}'.format(self.path_to_model, self.norm, new_norm))

    def rewrite_files(self, examples):
        """
        creates new .orig and .norm files for training (rewrites them with examples from annotated elans)
        examples is a list of pairs: ('transcription', 'normalization')
        """
        trns = '\n'.join([example[0].strip() for example in examples])
        nrms = '\n'.join([example[1].strip() for example in examples])

        with open('{}/{}'.format(self.path_to_model, self.orig), 'w', encoding='utf-8') as orig:
            orig.write(trns)
        with open('{}/{}'.format(self.path_to_model, self.norm), 'w', encoding='utf-8') as norm:
            norm.write(nrms)

    def retrain_model(self):
        os.system('python2 ' + self.path + 'preprocess.py ' + str(self.model))
        os.system('python2 ' + self.path + 'train.py ' + str(self.model))


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


class AnnotationMenuFromXML:
    def __init__(self, xml_name):
        path = os.path.join(settings.STATIC_ROOT, xml_name)
        self.tree = etree.parse(path)
        self.build_terms_dict()
        self.build_dep_dict()
        lemma_input_str = '<div class="manualAnnotationContainer"><label id="lemma_input">Lemma</label><input class="manualAnnotation" id="lemma_input" title="Lemma"></div>'
        form_input_str = '<div class="manualAnnotationContainer"><label id="form_input">Form</label><input class="manualAnnotation" id="form_input" title="Form"></div>'
        self.menu_html_str_1 = '<form style="display: table;">%s%s%s</form>' %(lemma_input_str, form_input_str, self.get_main_options())
        self.menu_html_str_2 = '<form>%s</form>' % self.get_extending_options()
        
    def build_terms_dict(self):
        self.terms_dict = {'ALLFORMS': {'newID':'ALLFORMS', 'propertyOf':'', 'extends':''}}

        for grammeme_tag in self.tree.xpath("grammeme"):
            name = grammeme_tag.xpath('name/text()')[0]
            try:
                newID = grammeme_tag.xpath('override/text()')[0]
            except IndexError:
                newID = name

            propertyOf = ''
            extends = ''
            if grammeme_tag.xpath('@propertyOf'):
                propertyOf = grammeme_tag.xpath('@propertyOf')[0]
            if grammeme_tag.xpath('@extends'):
                propertyOf = grammeme_tag.xpath('@extends')[0]

            self.terms_dict[name] = {'newID': newID, 'propertyOf': propertyOf, 'extends': extends}

    def build_dep_dict(self):
        self.dep_dict = {}
        for grammeme_tag in self.tree.xpath('grammeme[@toForms and not(@propertyOf)]'):
            label = grammeme_tag.xpath('label/text()')[0]
            id_raw = grammeme_tag.xpath('name/text()')[0]
            id_final = self.terms_dict[id_raw]['newID']
            dep_lst = grammeme_tag.xpath('@toForms')[0].split(',')
            option_tags = self.tree.xpath("grammeme[contains(@propertyOf,'%s')]" % id_raw)
            options = [self.terms_dict[option_tag.xpath('name/text()')[0]]['newID'] for option_tag in option_tags]
            self.dep_dict[tuple(options)] = {'ID': id_final, 'label': label, 'dep_lst': self.get_dependences(dep_lst)}

    def get_dependences(self, dep_lst_raw):
        dep_lst_final = []
        for item in dep_lst_raw:
            tags, index = item.split(':')
            index = int(index)
            tags_lst = list(map(lambda tag: self.terms_dict[tag]['newID'], tags.split('.')))
            dep_lst_final.append({'tags':tags_lst, 'index':index})
        return dep_lst_final

    def get_options_for_id(self, id_raw):
        options_str = '<option id="blank"></option>'
        for option_tag in self.tree.xpath("grammeme[contains(@propertyOf,'%s')]" %(id_raw)):
            option_id = self.terms_dict[option_tag.xpath('name/text()')[0]]['newID']
            options_str = "%s<option id='%s'>%s</option>" %(options_str, option_id, option_id)
        return options_str

    def get_main_options(self):
        main_options_tag_str = ''
        for grammeme_tag in self.tree.xpath('grammeme[@toForms and not(@propertyOf)]'):
            label = grammeme_tag.xpath('label/text()')[0]
            id_raw = grammeme_tag.xpath('name/text()')[0]
            id_final = self.terms_dict[id_raw]['newID']
            dep_lst = grammeme_tag.xpath('@toForms')[0].split(',')
            label_tag_str = '<label for="%s">%s</label>' % (id_final, label)
            select_tag_str = "<select class='manualAnnotation' id='%s' title='%s' data-dep='%s'>%s</select>" % (
                id_final,
                label,
                json.dumps(self.get_dependences(dep_lst)),
                self.get_options_for_id(id_raw)
            )
            main_options_tag_str = '%s<div class="manualAnnotationContainer">%s%s</div>' % (main_options_tag_str, label_tag_str, select_tag_str)
        return main_options_tag_str

    def get_extending_options(self):
        main_options_tag_str = ''
        for grammeme_tag in self.tree.xpath('grammeme[@extends and not(@propertyOf)]'):
            label = grammeme_tag.xpath('label/text()')[0]
            id_raw = grammeme_tag.xpath('name/text()')[0]
            id_final = self.terms_dict[id_raw]['newID']
            to_forms = grammeme_tag.xpath('@extends')[0].split(',')
            select_tag_str = "<label><input type='checkbox' class='manualAnnotation' name='%s' value='%s' data-dep='%s'>%s</label>" % (
                id_final,
                id_final,
                json.dumps(to_forms),
                label
            )
            main_options_tag_str = '%s<div class="manualAnnotationContainer">%s</div>' % (main_options_tag_str, select_tag_str)
        return main_options_tag_str

    def override_abbreviations(self, tag_str, is_lemma=False):
        tags_lst = [t for t in re.split('[, -]', tag_str) if t]
        if is_lemma:
            lemma, tags_lst = tags_lst[0], tags_lst[1:]

        for i in range(len(tags_lst)):
            try:
                tags_lst[i] = self.terms_dict[tags_lst[i]]['newID']
            except KeyError:
                pass

        new_tags = ['' for _ in range(6)]
        # TODO: this value in range should be replaced
        # TODO: with the actual maximum number of main tags for a particular category

        for tag in tags_lst:
            checked = False
            for options in self.dep_dict.keys():
                if tag not in options:
                    continue

                if self.dep_dict[options]['ID'] == 'POS':
                    pos = tag
                    new_tags[0] = tag
                    checked = True
                    break

                try:
                    dep_lst = self.dep_dict[options]['dep_lst']
                    for dep in dep_lst:
                        if pos not in dep['tags']:
                            continue

                        try:
                            new_tags[dep['index']] = tag
                        except IndexError:
                            new_tags.append(tag)

                        checked = True
                        break

                except NameError:
                    pass

            if checked is False:
                new_tags.append(tag)

        new_tags = [t for t in new_tags if t]
        if is_lemma:
            new_tags = [lemma] + new_tags

        new_tags = '-'.join(new_tags).replace(';-', '; ')
        return new_tags
