import re
import os
import json
from collections import defaultdict

from trimco.settings import _STATIC_ROOT
from .format_utils import ANNOTATION_TAG_SEP


class AnnotationMenu:
    def __init__(self, json_name):
        self.config = self._read_config(json_name)
        self.surface_tags_by_category = self._get_tags_by_category()

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
            f"<div id='manual_annotation' data-order='{json.dumps(self.config['order'])}'>"
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

        order = defaultdict(dict)
        for pos, orders in config['order'].items():
            for k, v in orders.items():
                k = k.replace(' ', '')
                order[pos][k] = {vv: i+1 for i, vv in enumerate(v)}
                order[pos][k]['part of speech'] = 0
        config['order'] = order

        return config

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
            categories = [cat.strip() for cat in tag_dict['categories'].split(',')]
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
        config_sets = [set(k) for k in order_config.keys()]
        tag_keyset = {f'{k}:{v}' for k, v in tags_dict.items()}

        order_key = 'default'
        for s in config_sets:
            if not s - tag_keyset:
                order_key = tuple(sorted(s))
                break

        return order_key

    def override_abbreviations(self, tag_str):
        tags_lst = [t for t in re.split(r'[, \-]', tag_str) if t]
        if not tags_lst:
            return ''

        tags_dict = {
            self.config['grammemes'][t]['category']: self.config['grammemes'][t]['surface_tag']
            for t in tags_lst if t in self.config['grammemes']
        }

        facultative = [  # todo: finalize list
            t for t in self.config['facultative'].keys()  # iterating through config to keep the order fixed
            if t in tags_lst
        ]

        pos = tags_dict.get('part of speech')
        if pos is None:  # UNKN, LATIN, PNCT
            return tag_str

        final_tags = [pos]
        if pos in self.config['order']:
            order_key = self.get_order_by_tag(pos, tags_dict)
            for key in self.config['order'][pos][order_key]:
                final_tags.append(tags_dict[key])

        final_tags.extend(facultative)

        final_tags = ANNOTATION_TAG_SEP.join(final_tags).replace(';-', '; ')  # todo: wtf
        return final_tags


annotation_menu = AnnotationMenu("annotation_grammemes.json")


if __name__ == '__main__':
    from pymorphy2 import MorphAnalyzer

    test_config = {
        'долг': 'NOUN-m-nom-sg',
        'долгу': 'NOUN-m-gen2-sg',
        'красивая': 'ADJF-f-nom-sg',
        'красивые': 'ADJF-nom-pl',
        'идут': 'VERB-ipfv-prs-ind-3-pl',
        'приехали': 'VERB-pfv-pst-ind-pl',
        'хорошо': 'ADV',
        'смотри': 'VERB-ipfv-imp-sg',
        'шла': 'VERB-ipfv-pst-ind-sg-f',
        'пятидесяти': 'NUMR-gen',
        'идти': 'INF-ipfv',
        'Новгород': 'NOUN-m-acc-sg-Geox',
        'Пети': 'NOUN-m-gen-sg-anim-Name',
        'МВД': 'NOUN-n-gen-sg-Abbr',
        'ВШЭ': 'UNKN'
    }

    m = MorphAnalyzer()
    for word, true_res in test_config.items():
        auto_annot = str(m.parse(word)[0].tag)
        overriden = annotation_menu.override_abbreviations(auto_annot)
        try:
            assert overriden == true_res
        except AssertionError:
            print('ERROR', word, true_res, overriden, sep='\t')
