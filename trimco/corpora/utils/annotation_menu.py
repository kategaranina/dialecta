import re
import os
import json
from collections import defaultdict

from trimco.settings import _STATIC_ROOT


class AnnotationMenu:
    def __init__(self, json_name):
        self.config = self._read_config(json_name)
        self.tags_by_category = self._get_tags_by_category()
        self.order_idxs = self._get_order_idxs()

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
            f'<form style="display: table;">'
            f'{lemma_input_str}'
            f'{form_input_str}'
            f'{"".join(self._get_main_options())}'
            f'</form>'
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
                if k != 'default':
                    parts = [part.strip() for part in k.split(',')]
                    k = tuple(sorted(parts))
                order[pos][k] = v

        config['order'] = order
        return config

    def _get_tags_by_category(self):
        tags_by_category = defaultdict(list)
        for tag, tag_dict in self.config['grammemes'].items():
            tags_by_category[tag_dict['category']].append(tag)
        return tags_by_category

    def _get_order_idxs(self):
        order_idxs_by_category = defaultdict(list)
        for pos, order_dict in self.config['order'].items():
            for order, categories in order_dict.items():
                req_tagset = [pos]
                if order != 'default':
                    req_tagset.extend([t.split(':', 1)[1] for t in order])

                for i, category in enumerate(categories):
                    order_idx = {'tags': req_tagset, 'index': i+1}
                    order_idxs_by_category[category].append(order_idx)

        order_idxs_by_category['part of speech'] = [{'tags': ['ALLFORMS'], 'index': 0}]
        return order_idxs_by_category

    def _get_main_options(self):
        main_options = []
        for category, tags in self.tags_by_category.items():
            options = ['<option id="blank"></option>']
            for tag in tags:
                surface_tag = self.config['grammemes'][tag]['surface_tag']
                options.append(f'<option id="{surface_tag}">{surface_tag}</option>')

            select_form = (
                f'<div class="manualAnnotationContainer">'
                f'<label for="{category}">{category.title()}</label>'
                f'<select class="manualAnnotation" '
                f'id={category} '
                f'title={category} '
                f'data-dep={json.dumps(self.order_idxs[category])}>'
                f'{"".join(options)}'
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
                f"name='{tag}' value='{tag}' data-dep='{categories}'>"
                f"{tag_dict['label']}"
                f"</label></div>"
            )
            facultative_options.append(tag_html)
        return facultative_options

    def _get_order(self, pos, tags_dict):
        order_config = self.config['order'][pos]
        config_sets = [set(k) for k in order_config.keys()]
        tag_keyset = {f'{k}:{v}' for k, v in tags_dict.items()}

        order_key = 'default'
        for s in config_sets:
            if not s - tag_keyset:
                order_key = tuple(sorted(s))
                break

        return order_key

    def override_abbreviations(self, tag_str, is_lemma=False):
        tags_lst = [t for t in re.split('[, -]', tag_str) if t]
        if not tags_lst:
            return ''

        if is_lemma:
            lemma, tags_lst = tags_lst[0], tags_lst[1:]

        tags_dict = {
            self.config['grammemes'][t]['category']: self.config['grammemes'][t]['surface_tag']
            for t in tags_lst if t in self.config['grammemes']
        }

        facultative = [  # todo: finalize list
            t for t in self.config['facultative'].keys()  # iterating through config to keep the order fixed
            if t in tags_lst
        ]

        pos = tags_dict['part_of_speech']  # must always be there
        final_tags = [pos]
        if pos in self.config['order']:
            order_key = self._get_order(pos, tags_dict)
            for key in self.config['order'][pos][order_key]:
                final_tags.append(tags_dict[key])

        final_tags.extend(facultative)

        if is_lemma:
            final_tags = [lemma] + final_tags

        # TODO: import ANNOTATION_TAG_SEP
        final_tags = '-'.join(final_tags).replace(';-', '; ')  # todo: wtf
        return final_tags


annotation_menu = AnnotationMenu("annotation_grammemes.json")
