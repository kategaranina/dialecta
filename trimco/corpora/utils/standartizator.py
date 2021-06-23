import os
import pymorphy2
import datetime
from collections import defaultdict, Counter
from django.conf import settings
from normalization.models import Model, Word
from .word_list import find_word, find_standartization
from .annotation_menu import annotation_menu
from .format_utils import UNKNOWN_PREFIX, ANNOTATION_TAG_SEP


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
            lemma, tag = full_tag.split(ANNOTATION_TAG_SEP, 1)
            score = count / total_anns
            result_list.append([lemma, tag, score])

        return result_list

    def get_annotation_options_list_by_parsing(self, orig, standartization):
        result_list = []

        for annot in self.morph_rus.parse(standartization):
            if annot.score <= 0.001:
                continue

            tag = annotation_menu.override_abbreviations(str(annot.tag))

            # TODO: move somewhere
            if self.model.name == 'be' and (orig.endswith('ṷšy') or orig.endswith('ṷši')) and tag.startswith('GER-'):
                tag = 'ANTP' + ANNOTATION_TAG_SEP + tag[4:]

            # pymorphy2 specific
            methods = {str(x[0]) for x in annot.methods_stack}
            lemma = annot.normal_form if methods == {'<DictionaryAnalyzer>'} else UNKNOWN_PREFIX + annot.normal_form

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
