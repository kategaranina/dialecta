import re
import os
import json
from lxml import etree
from django.conf import settings


class AnnotationMenuFromXML:
    def __init__(self, xml_name):
        path = os.path.join(settings.STATICFILES_DIRS[0], xml_name)
        self.tree = etree.parse(path)
        self.build_terms_dict()
        self.build_dep_dict()
        lemma_input_str = '<div class="manualAnnotationContainer"><label id="lemma_input">Lemma</label><input class="manualAnnotation" id="lemma_input" title="Lemma"></div>'
        form_input_str = '<div class="manualAnnotationContainer"><label id="form_input">Form</label><input class="manualAnnotation" id="form_input" title="Form"></div>'
        self.menu_html_str_1 = '<form style="display: table;">%s%s%s</form>' % (
            lemma_input_str, form_input_str, self.get_main_options()
        )
        self.menu_html_str_2 = '<form>%s</form>' % self.get_extending_options()

    def build_terms_dict(self):
        self.terms_dict = {'ALLFORMS': {'newID': 'ALLFORMS', 'propertyOf': '', 'extends': ''}}

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
            dep_lst_final.append({'tags': tags_lst, 'index': index})
        return dep_lst_final

    def get_options_for_id(self, id_raw):
        options_str = '<option id="blank"></option>'
        for option_tag in self.tree.xpath("grammeme[contains(@propertyOf,'%s')]" % (id_raw)):
            option_id = self.terms_dict[option_tag.xpath('name/text()')[0]]['newID']
            options_str = "%s<option id='%s'>%s</option>" % (options_str, option_id, option_id)
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
            main_options_tag_str = '%s<div class="manualAnnotationContainer">%s%s</div>' % (
            main_options_tag_str, label_tag_str, select_tag_str)
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
            main_options_tag_str = '%s<div class="manualAnnotationContainer">%s</div>' % (
            main_options_tag_str, select_tag_str)
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

        # TODO: import ANNOTATION_TAG_SEP
        new_tags = '-'.join(new_tags).replace(';-', '; ')
        return new_tags

    def build_annotation_menu(self):
        return [
            self.menu_html_str_1,
            self.menu_html_str_2
        ]


annotation_menu = AnnotationMenuFromXML("grammemes_pymorphy2.xml")
