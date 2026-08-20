from corpora.utils.db_utils import WORD_COLLECTION, STANDARTIZATION_COLLECTION, SENTENCE_COLLECTION


print('words', WORD_COLLECTION.count_documents({}))
print('std', STANDARTIZATION_COLLECTION.count_documents({}))
print('sentences', SENTENCE_COLLECTION.count_documents({}))

r_sents = list(SENTENCE_COLLECTION.find({'elan': "MP-BRAR-03-01-01.eaf"}))
r_words = list(WORD_COLLECTION.find({'word': "i"}))

print('sentences for MP-BRAR-03-01-01.eaf', len(r_sents))
print('words for i', len(r_words), len(r_words[0]['standartizations']))

