import re
from lxml import etree


ANNOTATION_WORD_SEP = '|'
ANNOTATION_PART_SEP = ':'
ANNOTATION_TAG_SEP = '-'
UNKNOWN_PREFIX = '(unkn)_'

STANDARTIZATION_REGEX = re.compile(r'^(.+?)_standartization$')
STANDARTIZATION_NUM_REGEX = re.compile(r'^(\d+):(.+)')
ANNOTATION_NUM_REGEX = re.compile(r'(\d+?):(.+?):(.+)')

TECH_REGEX = re.compile(r'(?:\.\.\.|\?|\[|]|\.|!|un\'?int\.?)+')


def get_participant_status(tier_name):
    if '_i_' in tier_name:
        return 'inwr'
    elif '_n_' in tier_name:
        return 'inwd'
    return ''


def get_participant_tag_and_status(participant, tier_name):
    participant = participant.title()
    participant = filter(None, participant.split(' '))
    participant = '. '.join(namepart[0] for namepart in participant) + '.'
    tier_status = get_participant_status(tier_name)
    return participant, tier_status


def get_audio_annot_div(stttime, endtime):
    return '<div class="audiofragment" starttime="%s" endtime="%s"><button class="fa fa-spinner off"></button></div>' % (stttime, endtime)


def get_audio_link(audio_file_path):
    return '<audio id="elan_audio" src="/media/%s" preload></audio>' % audio_file_path


def prettify_transcript(transcript):
    if not transcript[-1].strip():
        transcript = transcript[:-1]

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


def add_annotation_to_transcript(transcript, normz_tokens_dict, annot_tokens_dict):
    i = 0
    transcript_obj = etree.fromstring('<c>'+transcript+'</c>')

    for tag in transcript_obj.iterchildren():
        if tag.tag != 'token':
            continue

        if i in annot_tokens_dict.keys():
            morph = annot_tokens_dict[i][1]
            tag.insert(0, etree.fromstring('<morph>' + morph + '</morph>'))

            lemma = annot_tokens_dict[i][0]
            tag.insert(0, etree.fromstring('<lemma>' + lemma + '</lemma>'))

        if i in normz_tokens_dict.keys():
            tag.insert(0, etree.fromstring('<nrm>' + normz_tokens_dict[i][0] + '</nrm>'))

        i += 1

    return etree.tostring(transcript_obj)[3:-4].decode('utf-8')


def get_annot_div(tier_name, dialect, participant, transcript, normz_tokens_dict, annot_tokens_dict, elan_file=None):
    transcript = prettify_transcript(transcript)
    if annot_tokens_dict:
        transcript = add_annotation_to_transcript(transcript, normz_tokens_dict, annot_tokens_dict)

    participant_div = '<span class="participant">%s</span>' % participant
    transcript_div = '<span class="transcript">%s</span>' % transcript

    if elan_file:
        elan_attr = 'elan="%s"' % elan_file
        recording = elan_file.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        recording_div = '<span class="recording">%s</span>' % recording
    else:
        elan_attr, recording_div = '', ''

    annot_div = '<div class="annot" tier_name="%s" dialect="%s" %s><div class="meta">%s%s</div>%s</div>' % \
                (tier_name, dialect, elan_attr, participant_div, recording_div, transcript_div)

    return annot_div
