import re
import os
import json
from collections import defaultdict

from trimco.settings import _STATIC_ROOT
from .format_utils import ANNOTATION_TAG_SEP


class AnnotationMenu:
    tag_sep = ','

    def __init__(self, json_name):
        self.config = self._read_config(json_name)
        self.surface_tags_by_category = self._get_tags_by_category()
        self._parse_config_order()

        lemma_input_str = (
            '<div class="manualAnnotationContainer">'
            '<label id="lemma_input">Lemma</label>'
            '<input class="manualAnnotation" id="lemma_input" title="Lemma">'
            '</div>'
        )
        form_input_str = (
            '<div class="manualAnnotationContainer">'
            '<label id="form_input">Form</label>'
            '<input class="manualAnnotation" id="form_input" title="Form">'
            '</div>'
        )

        self.menu_html_str_1 = (
            f"<div id='manual_annotation' data-order='{self._serialize_config_order()}'>"
            f"<span>Manual annotation</span>"
            f"<form style='display: table;'>"
            f"{lemma_input_str}"
            f"{form_input_str}"
            f"{''.join(self._get_main_options())}"
            f"</form>"
            f"</div>"
        )
        self.menu_html_str_2 = (
            f'<form>'
            f'{"".join(self._get_facultative_options())}'
            f'</form>'
        )

    @staticmethod
    def _read_config(json_name):
        with open(os.path.join(_STATIC_ROOT, json_name)) as f:
            config = json.load(f)
        return config

    def _parse_config_order(self):
        order = defaultdict(dict)
        for pos, orders in self.config['order'].items():
            order[pos] = {tuple(k.split(self.tag_sep)): v for k, v in orders.items()}
        self.config['order'] = order

    def _serialize_config_order(self):
        serialized = {}
        for pos, orders in self.config['order'].items():
            serialized[pos] = {self.tag_sep.join(k): v for k, v in orders.items()}

        return json.dumps(serialized)

    def _get_tags_by_category(self):
        tags_by_category = defaultdict(list)
        for tag, tag_dict in self.config['grammemes'].items():
            surface_tag = tag_dict['surface_tag']
            if surface_tag not in tags_by_category[tag_dict['category']]:
                tags_by_category[tag_dict['category']].append(surface_tag)
        return tags_by_category

    def _get_main_options(self):
        main_options = []
        for category, tags in self.surface_tags_by_category.items():
            options = ['<option id="blank"></option>']
            for tag in tags:
                options.append(f'<option id="{tag}">{tag}</option>')

            select_form = (
                f"<div class='manualAnnotationContainer'>"
                f"<label for='{category}'>{category.title()}</label>"
                f"<select class='manualAnnotation' "
                f"id='{category}' "
                f"title='{category}'>"
                f"{''.join(options)}"
                f'</select></div>'
            )
            main_options.append(select_form)

        return ''.join(main_options)

    def _get_facultative_options(self):
        facultative_options = []
        for tag, tag_dict in self.config['facultative'].items():
            categories = tag_dict['categories']
            tag_html = (
                f"<div class='manualAnnotationContainer'><label>"
                f"<input type='checkbox' class='manualAnnotation' "
                f"name='{tag}' value='{tag}' data-dep='{json.dumps(categories)}'>"
                f"{tag_dict['label']}"
                f"</label></div>"
            )
            facultative_options.append(tag_html)
        return facultative_options

    def build_annotation_menu(self):
        return [
            self.menu_html_str_1,
            self.menu_html_str_2
        ]

    def get_order_by_tag(self, pos, tags_dict):
        order_config = self.config['order'][pos]
        tag_keyset = set(tags_dict.values())

        order_key = ('default',)
        for config_order_k in order_config:
            if not set(config_order_k) - tag_keyset:
                order_key = config_order_k
                break

        return order_config[order_key]

    def order_compulsory_tags(self, pos, tags_dict, tag_str):
        final_tags = [pos]

        if pos in self.config['order']:
            order = self.get_order_by_tag(pos, tags_dict)
            for key in order:
                key_always_required = True
                if key.startswith('*'):
                    key_always_required = False
                    key = key[1:]

                if key not in tags_dict and key_always_required:
                    print('WARNING', key + ' not in tags ' + tag_str)
                    final_tags.append('')
                    continue

                if key in tags_dict or key_always_required:
                    final_tags.append(tags_dict[key])

        return final_tags

    def order_facultative_tags(self, facultative_tags, compulsory_tags, word=None):
        all_tags = compulsory_tags + facultative_tags

        def tag_suitable(tag, v):
            if tag not in facultative_tags:
                return False

            is_for_all = v['categories'][0] == "ALLFORMS"
            is_in_category = any(
                all(cat in all_tags for cat in cats.split('.'))
                for cats in v['categories']
            )
            if not (is_for_all or is_in_category):
                print("facultative present but is not allowed by category\n", tag, all_tags, word, "\n")

            return is_for_all or is_in_category

        facultative = [
            t for t, v in self.config['facultative'].items()  # iterating through config to keep the order fixed
            if tag_suitable(t, v)
        ]
        return facultative

    def override_abbreviations(self, tag_str):
        tags_lst = [t for t in re.split(r'[, ]', tag_str) if t]
        if not tags_lst:
            return ''

        tags_dict = {
            self.config['grammemes'][t]['category']: self.config['grammemes'][t]['surface_tag']
            for t in tags_lst if t in self.config['grammemes']
        }
        facultative_lst = [t for t in tags_lst if t in self.config['facultative']]

        pos = tags_dict.get('part of speech')
        if pos is None:  # UNKN, LATIN, PNCT
            return tag_str

        final_tags = self.order_compulsory_tags(pos, tags_dict, tag_str)
        facultative = self.order_facultative_tags(facultative_lst, final_tags)
        final_tags.extend(facultative)

        final_tags = ANNOTATION_TAG_SEP.join(final_tags).replace(';-', '; ')  # todo: wtf
        return final_tags


annotation_menu = AnnotationMenu("annotation_grammemes.json")


if __name__ == '__main__':
    from pymorphy2 import MorphAnalyzer

    test_config = {
        'долг': 'NOUN-m-nom-sg-inan',
        'долгу': 'NOUN-m-gen2-sg-inan',
        'красивая': 'ADJF-f-nom-sg',
        'красивые': 'ADJF-nom-pl',
        'идут': 'VERB-ipfv-prs-ind-3-pl',
        'приехали': 'VERB-pfv-pst-ind-pl',
        'хорошо': 'ADV',
        'смотри': 'VERB-ipfv-imp-sg',
        'шла': 'VERB-ipfv-pst-ind-sg-f',
        'пятидесяти': 'NUMR-gen',
        'обе': 'NUMR-f-nom',
        'идти': 'INF-ipfv',
        'она': 'NPRO-f-nom-3-sg',
        'я': 'NPRO-nom-1-sg',
        'Новгород': 'NOUN-m-acc-sg-inan-Geox',
        'Пети': 'NOUN-m-gen-sg-anim-Name',
        'МВД': 'NOUN-n-gen-sg-inan-Abbr-Sgtm-Fixd',
        'ВШЭ': 'UNKN',
    }

    m = MorphAnalyzer()
    for word, true_res in test_config.items():
        auto_annot = str(m.parse(word)[0].tag)
        overriden = annotation_menu.override_abbreviations(auto_annot)
        try:
            assert overriden == true_res
        except AssertionError:
            print('ERROR', word, true_res, overriden, sep='\t')
