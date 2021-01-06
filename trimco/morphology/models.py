from django.db import models


class GlossingRule(models.Model):
    abbreviation = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    examples = models.TextField(blank=True)
    abbr_overrides = models.CharField(max_length=100, blank=True)
    section = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.abbreviation

    def populate(self, abbreviation, description, examples, abbr_overrides, section):
        self.abbreviation = abbreviation
        self.description = description
        self.examples = examples
        self.abbr_overrides = abbr_overrides
        self.section = section
        self.save()


class Language(models.Model):
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=5)

    def __str__(self):
        return self.abbreviation


class Dialect(models.Model):
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)
    to_language = models.ForeignKey('Language')
    description = models.TextField(blank=True)

    def __str__(self):
        return self.abbreviation


class Lemma(models.Model):
    value = models.CharField(max_length=30)
    POS = models.CharField(max_length=10)
    to_language = models.ForeignKey('Language')
    
    class Meta:
        verbose_name_plural = 'Lemmata'

    def __str__(self):
        return self.value


class Form(models.Model):
    value = models.CharField(max_length=30)
    to_lemma = models.ForeignKey(Lemma, verbose_name='to lemma(ta)')
    annotation = models.CharField(max_length=30)
    
    def __str__(self):
        return self.value


class TokenToForm(models.Model):
    order_id = models.IntegerField()
    to_form = models.ForeignKey('Form')
    to_token = models.ForeignKey('Token')


class Token(models.Model):
    transcription = models.CharField(max_length=50)
    to_forms = models.ManyToManyField('Form', through='TokenToForm')


class NormalizationModel(models.Model):
    to_dialect = models.ManyToManyField('Dialect')
    to_additional_language = models.ForeignKey('Language', blank=True, null=True)
    examples = models.TextField(blank=True)
    exceptions = models.TextField(blank=True)

    def __str__(self):
        return ', '.join([x.abbreviation for x in self.to_dialect.all()])
