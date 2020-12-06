import re

import pymongo

from trimco.settings import MONGO_URL, MONGO_DB_NAME


MONGO_CLIENT = pymongo.MongoClient(MONGO_URL)
MONGO_DB = MONGO_CLIENT[MONGO_DB_NAME]
WORD_COLLECTION = MONGO_DB['words']

ANNOTATION_WORD_SEP = '|'
ANNOTATION_OPTION_SEP = '/'


def clean_transcription(transcription):
    return re.sub(r'\.\.\.|\?|\[|\]|\.|!|un\'?int\.?', '', transcription).strip()
