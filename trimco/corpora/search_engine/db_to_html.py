from corpora.utils.format_utils import (
    get_audio_link, get_audio_annot_div,
    get_annot_div, get_participant_status
)


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
            participant=item['speaker'],
            transcript=transcript,
            normz_tokens_dict=normz_tokens_dict,
            annot_tokens_dict=annot_tokens_dict
        )

        audio_annot_div = get_audio_annot_div(item['audio']['start'], item['audio']['end'])
        participant_status = get_participant_status(item['tier'])
        annot_wrapper_div = '<div class="annot_wrapper %s">%s%s</div>' % (participant_status, audio_annot_div, annot_div)

        audio_div = get_audio_link(item['audio']['file'])
        item_div = audio_div + annot_wrapper_div
        item_divs.append(item_div)

    return ''.join(item_divs)
