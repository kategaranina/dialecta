from django.db import models
from geoposition.fields import GeopositionField
from django.core.exceptions import ObjectDoesNotExist
from morphology.models import Language


SEX_CHOICES = (
    ('m', 'Male'),
    ('f', 'Female'),
    ('u', 'Unspecified'),
)


class Location(models.Model):
    name = models.CharField(max_length=100)
    position = GeopositionField()

    def __str__(self):
        return self.name


class Interviewer(models.Model):
    last_name = models.CharField(max_length=15)
    first_name = models.CharField(max_length=15)
    patronimic_name = models.CharField(max_length=20, blank=True)
    year_of_birth = models.IntegerField(null=True)
    year_of_enrollment = models.IntegerField(null=True)
    affiliation = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=40)


class Speaker(models.Model):
    string_id = models.CharField(max_length=10, verbose_name='Speaker ID')  # A
    last_name = models.CharField(max_length=15)  # E
    first_name = models.CharField(max_length=15)  # C
    patronimic_name = models.CharField(max_length=20, blank=True)  # D
    other_names = models.CharField(max_length=40, blank=True)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)  # F - change ж to f, м to m
    year_of_birth = models.IntegerField(null=True)  # D
    year_of_death = models.IntegerField(blank=True, null=True)
    locations = models.ManyToManyField('Location', through='LocationRelation')

    # ONLY for import from google docs
    pob = models.CharField(max_length=200, blank=True, verbose_name='Old Field: Place of Birth')  # H
    por = models.CharField(max_length=200, blank=True, verbose_name='Old Field: Residence')  # I
    pofr = models.CharField(max_length=200, blank=True, verbose_name='Old Field: Former Residence')  # J
    mob = models.CharField(max_length=80, blank=True, verbose_name='Old Field: Mobility')  # K

    mobility = models.IntegerField(blank=True, null=True)
    education = models.ForeignKey('EducationType', blank=True, null=True)

    # used during import:
    education_text = models.TextField(blank=True, verbose_name='Education details')  # M

    relations = models.ManyToManyField(
        'self',
        through='PersonalRelation',
        symmetrical=False,
        through_fields=('from_speaker', 'to_speaker')
    )
    languages = models.ManyToManyField(Language, through='LanguageRelation')

    # used during import:
    profession = models.CharField(max_length=200, blank=True)  # L

    # ONLY for import from google docs
    relatives = models.CharField(max_length=200, verbose_name='Old Field: Relatives')  # O
    parents = models.CharField(max_length=200, verbose_name='Old Field: Parents')  # R

    photo = models.ImageField(blank=True, null=True)

    # used during import for Примечания
    details = models.TextField(blank=True,)  # P

    def __str__(self):
        patr = self.patronimic_name or ''
        return '%s: %s, %s %s %s' % (self.string_id, self.last_name, self.first_name, patr, self.year_of_birth)

    def photo_preview(self):
        if self.photo.url:
            return '<img src="%s" style="height:100px; width:100px;"/>' % self.photo.url
        return ''

    photo_preview.allow_tags = True

    def place_of_birth(self):
        try:
            return self.locations.all().filter(locationrelation__place_of_birth=True)[0].name
        except IndexError:
            return ''

    def get_relations(self):
        return Speaker.objects.select_related('relations')

    class Meta:
        ordering = ['string_id']


class RelationType(models.Model):
    name = models.CharField(max_length=20)
    abbreviation = models.CharField(max_length=2)
    assymetric_relation = models.OneToOneField(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name='Assymetric reversed relation'
    )

    def __str__(self):
        if self.assymetric_relation is not None:
            return '%s <> %s' % (self.name, self.assymetric_relation.name)
        return '%s <> %s' % (self.name, self.name)


class EducationType(models.Model):
    name = models.CharField(max_length=30)
    abbreviation = models.CharField(max_length=5)

    def __str__(self):
        return self.name


class PersonalRelation(models.Model):
    """
    Model of defining relations between speakers
    
    Include overrides of model save and delete functions
    that additionaly create, edit and delete a
    reverse relation that mirrors the one being modified.

    Relation types are included in RelationType
    Asymmetrc relation types are specified in RelationType.assymetric_relation

    RELATION_CHOICES:
       ('ch', 'child'),
       ('pr', 'parent'),
       ('sp', 'spouse'),
       ('sb', 'sibling'),
       ('gc', 'grandchild'),
       ('gp', 'grandparent'),
       ('fr', 'friend'),
       ('ng', 'neighbor'),
       ('lv', 'lover')

    ASYMMETRIC_RELATIONS:
       'child': 'parent',
       'parent': 'child',
       'grandchild': 'grandparent',
       'grandparent': 'grandchild',
    """
    relation_type = models.ForeignKey(RelationType)
    from_speaker = models.ForeignKey('Speaker')
    to_speaker = models.ForeignKey('Speaker', related_name='related_speaker')
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'VII. Relations with other speakers'

    def save(self, *args, **kwargs):
        older_rev_rel_obj = self.get_reversed_relation_obj()
        super(PersonalRelation, self).save(*args, **kwargs)

        if self.get_reversed_relation_obj() is None:
            if older_rev_rel_obj is not None:
                older_rev_rel_obj.delete()
            self.create_reversed_relation()

        else:
            self.update_reversed_relation()
        
    def delete(self, *args, **kwargs):
        rev_rel_obj = self.get_reversed_relation_obj()
        super(PersonalRelation, self).delete(*args, **kwargs)
        if rev_rel_obj is not None:
            rev_rel_obj.delete()

    def update_reversed_relation(self):
        rev_rel_obj = self.get_reversed_relation_obj()
        if rev_rel_obj.relation_type != self.get_reversed_relation_type() or rev_rel_obj.notes != self.notes:
            rev_rel_obj.relation_type = self.get_reversed_relation_type()
            rev_rel_obj.notes = self.notes
            rev_rel_obj.save()

    def get_reversed_relation_obj(self):
        try:
            rev_rel_obj = PersonalRelation.objects.get(
                from_speaker=self.to_speaker,
                to_speaker=self.from_speaker
                )
            return rev_rel_obj

        except ObjectDoesNotExist:
            return

    def create_reversed_relation(self):
        rev_rel_obj = PersonalRelation(
            from_speaker=self.to_speaker,
            to_speaker=self.from_speaker,
            relation_type=self.get_reversed_relation_type(),
            notes=self.notes,
        )
        rev_rel_obj.save()
        
    def get_reversed_relation_type(self):
        if self.relation_type.assymetric_relation is not None:
            return self.relation_type.assymetric_relation
        return self.relation_type


class LocationRelation(models.Model):
    to_speaker = models.ForeignKey('Speaker')
    to_location = models.ForeignKey('Location', verbose_name='Location')
    duration = models.IntegerField(verbose_name='Duration of stay (years)', blank=True, null=True)

    place_of_birth = models.BooleanField()
    living = models.BooleanField()
    working = models.BooleanField()
    studying = models.BooleanField()
    military_service = models.BooleanField()
    prison = models.BooleanField()
    details = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Geography of Life'


class LanguageRelation(models.Model):
    to_speaker = models.ForeignKey('Speaker')
    to_language = models.ForeignKey(Language, verbose_name='Language')
    native_speaker = models.BooleanField()
    literate = models.BooleanField()

    class Meta:
        verbose_name_plural = 'Linguistic Biography'
