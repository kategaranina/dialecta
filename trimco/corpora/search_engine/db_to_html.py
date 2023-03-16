from decimal import Decimal

from lxml import etree

from corpora.utils.db_utils import SENTENCE_COLLECTION
from corpora.utils.format_utils import (
    ANNOTATION_OPTION_SEP, ANNOTATION_TAG_SEP,
    TECH_REGEX, get_audio_link, get_audio_annot_div,
    get_annot_div, get_participant_tag_and_status
)
from corpora.utils.elan_utils import split_ann_for_db


def get_transcript_and_tags_dicts(words):
    transcript = []
    normz_tokens_dict = {}
    annot_tokens_dict = {}
    i = -1
    for w in words:
        transcript.append(w['transcription_view'])

        if TECH_REGEX.match(w['transcription_view']) is not None:
            continue

        i += 1
        standartization = w.get('standartization_view')
        if standartization is None:
            continue

        normz_tokens_dict[i] = [standartization]

        lemmata = []
        annots = []
        for ann in w.get('annotations', []):  # todo: 'annotations' will now contain only one element
            if ann['lemma_view'] not in lemmata:
                lemmata.append(ann['lemma_view'])
            annots.append(ann['tags_view'])

        annot_tokens_dict[i] = [
            ''.join(lemmata),
            ''.join(annots)
        ]

    return ' '.join(transcript), normz_tokens_dict, annot_tokens_dict


def db_response_to_html(results, reverse=False):
    if results is None:
        return '<div id="no_result">Empty search query.</div>', {}

    item_divs = []
    page_info = {}

    for i, item in enumerate(results):
        if not i:
            page_info['min'] = {
                'elan': item['elan'],
                'audio_start': item['audio']['start']
            }

        transcript, normz_tokens_dict, annot_tokens_dict = get_transcript_and_tags_dicts(item['words'])
        participant, participant_status = get_participant_tag_and_status(item['speaker'], item['tier'])
        annot_div = get_annot_div(
            tier_name=item['tier'],
            dialect=item['dialect'],
            participant=participant,
            transcript=transcript,
            normz_tokens_dict=normz_tokens_dict,
            annot_tokens_dict=annot_tokens_dict,
            elan_file=item['elan']
        )

        audio_annot_div = get_audio_annot_div(item['audio']['start'], item['audio']['end'])
        annot_wrapper_div = '<div class="annot_wrapper %s">%s%s</div>' % (participant_status, audio_annot_div, annot_div)

        audio_div = get_audio_link(item['audio']['file'])
        item_div = audio_div + annot_wrapper_div
        item_divs.append(item_div)

        page_info['max'] = {
            'elan': item['elan'],
            'audio_start': item['audio']['start']
        }

    if reverse and item_divs:
        item_divs = item_divs[::-1]
        page_info['min'], page_info['max'] = page_info['max'], page_info['min']

    return ''.join(item_divs) or '<div id="no_result">Nothing found.</div>', page_info


def process_html_token(token_el):
    word_dict = {}

    if token_el.tag in ['note', 'tech']:
        trt = token_el.text
        if token_el.tag == 'note':
            trt = '[' + trt + ']'
        word_dict['transcription_view'] = trt
        word_dict['transcription'] = trt
        return word_dict

    trt_lst = token_el.xpath('trt/text()')
    nrm_lst = token_el.xpath('nrm/text()')
    lemma_lst = token_el.xpath('lemma/text()')
    morph_lst = token_el.xpath('morph/text()')

    if not trt_lst:
        word_dict['transcription_view'] = token_el.text
        word_dict['transcription'] = token_el.text.lower()
        return word_dict

    word_dict['transcription_view'] = trt_lst[0]
    word_dict['transcription'] = trt_lst[0].lower()

    if nrm_lst:
        word_dict['standartization_view'] = nrm_lst[0]
        word_dict['standartization'] = nrm_lst[0].lower()

    if lemma_lst and morph_lst:
        word_dict['annotations'] = split_ann_for_db((lemma_lst[0], morph_lst[0]))

    return word_dict


def html_to_db(html_result):
    html_obj = etree.fromstring(html_result)
    for el in html_obj.xpath('//*[contains(@class,"annot_wrapper") and contains(@class, "changed")]'):
        elan_name = el.xpath('*[@class="annot"]/@elan')[0]
        tier_name = el.xpath('*[@class="annot"]/@tier_name')[0]
        start = int(Decimal(el.xpath('*[@class="audiofragment"]/@starttime')[0]))
        end = int(Decimal(el.xpath('*[@class="audiofragment"]/@endtime')[0]))

        words = []
        for token in el.xpath('*//*[self::token or self::tech or self::note]'):
            word_dict = process_html_token(token)
            words.append(word_dict)

        filter_query = {'elan': elan_name, 'tier': tier_name, 'audio.start': start, 'audio.end': end}
        update_query = {'$set': {'words': words}}
        SENTENCE_COLLECTION.update_one(filter_query, update_query)
