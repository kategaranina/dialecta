from decimal import Decimal

from lxml import etree

from corpora.utils.db_utils import SENTENCE_COLLECTION
from corpora.utils.format_utils import (
    get_audio_link, get_audio_annot_div,
    get_annot_div, get_participant_status
)
from corpora.utils.elan_utils import ANNOTATION_OPTION_SEP


def get_transcript_and_tags_dicts(words):
    transcript = []
    normz_tokens_dict = {}
    annot_tokens_dict = {}
    for i, w in enumerate(words):
        transcript.append(w['transcription'])

        standartization = w.get('standartization')
        if standartization is None:
            continue

        normz_tokens_dict[i] = [standartization]

        lemmata = []
        annots = []
        for ann in w.get('annotations', []):
            if ann['lemma'] not in lemmata:
                lemmata.append(ann['lemma'])
            full_ann = '-'.join([ann['lemma']] + ann['tags'])
            annots.append(full_ann)
        annot_tokens_dict[i] = ['/'.join(lemmata), '/'.join(annots)]

    return ' '.join(transcript), normz_tokens_dict, annot_tokens_dict


def db_response_to_html(results):
    item_divs = []

    for item in results:
        transcript, normz_tokens_dict, annot_tokens_dict = get_transcript_and_tags_dicts(item['words'])
        annot_div = get_annot_div(
            tier_name=item['tier'],
            dialect=item['dialect'],
            participant=item['speaker'],
            transcript=transcript,
            normz_tokens_dict=normz_tokens_dict,
            annot_tokens_dict=annot_tokens_dict,
            elan_file=item['elan']
        )

        audio_annot_div = get_audio_annot_div(item['audio']['start'], item['audio']['end'])
        participant_status = get_participant_status(item['tier'])
        annot_wrapper_div = '<div class="annot_wrapper %s">%s%s</div>' % (participant_status, audio_annot_div, annot_div)

        audio_div = get_audio_link(item['audio']['file'])
        item_div = audio_div + annot_wrapper_div
        item_divs.append(item_div)

    return ''.join(item_divs)


def process_html_token(token_el):
    word_dict = {}
    trt_lst = token_el.xpath('trt/text()')
    nrm_lst = token_el.xpath('nrm/text()')
    morph_lst = token_el.xpath('morph_full/text()')

    if not trt_lst:
        return word_dict

    word_dict['transcription'] = trt_lst[0].lower()

    if nrm_lst:
        word_dict['standartization'] = nrm_lst[0].lower()

    if morph_lst:
        anns = morph_lst[0].lower().split(ANNOTATION_OPTION_SEP)
        word_dict['annotations'] = [
            {'lemma': ann.split('-')[0], 'tags': ann.split('-')[1:]}
            for ann in anns
        ]

    return word_dict


def html_to_db(html_result):
    html_obj = etree.fromstring(html_result)
    for el in html_obj.xpath('//*[contains(@class,"annot_wrapper")]'):
        elan_name = el.xpath('*[@class="annot"]/@elan')[0]
        tier_name = el.xpath('*[@class="annot"]/@tier_name')[0]
        start = int(Decimal(el.xpath('*[@class="audiofragment"]/@starttime')[0]))
        end = int(Decimal(el.xpath('*[@class="audiofragment"]/@endtime')[0]))

        words = []
        for token in el.xpath('*//token'):
            word_dict = process_html_token(token)
            words.append(word_dict)

        filter_query = {'elan': elan_name, 'tier': tier_name, 'audio.start': start, 'audio.end': end}
        update_query = {'$set': {'words': words}}
        SENTENCE_COLLECTION.update_one(filter_query, update_query)
