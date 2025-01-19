from .format_utils import ANNOTATION_TAG_SEP


def correct_reflexive(norm, parser):
    if not norm.lower().endswith('ся'):
        return norm

    vowels = set('аеёиоуыэюя')

    if len(norm) > 2 and norm[-3] in vowels:
        if len(norm) > 3 and norm[-4] not in vowels:  # participles
            new_norm = norm[:-1] + 'ь'
            ann = parser.parse(new_norm)[0]
            ann_methods = {str(x[0]) for x in ann.methods_stack}

            if ann.tag.POS == 'VERB' or ann_methods != {'<DictionaryAnalyzer>'}:
                return new_norm

    return norm


def correct_antp(model_name, orig, tag):
    if model_name == 'be' and (orig.endswith('ṷšy') or orig.endswith('ṷši')) and tag.startswith('GER-'):
        tag = 'ANTP' + ANNOTATION_TAG_SEP + tag[4:]

    return tag


def check_for_pred(norm, tag, words_pred):
    if norm.lower() in words_pred:
        tag += ANNOTATION_TAG_SEP + 'orPRED'
    return tag


def override_tag(norm, tag, overrides_dict):
    if norm in overrides_dict:
        tag = overrides_dict[norm]
    return tag
