from django.db import models
from morphology.models import Dialect
from corpora.models import Recording
#from morphology.models import *
from django.utils.safestring import mark_safe


class Model(models.Model):

  name = models.CharField(max_length=10) #!this should correspond to the actual folder name of the model inside csmtiser normalizer !
  to_dialect = models.ManyToManyField(Dialect, blank=True,
                                      verbose_name='Dialect')
  recordings_to_retrain = models.ManyToManyField(Recording, blank=True)

  def __str__(self):
    return self.name

  def retrain_model(self):
    print(self.recordings_to_retrain.all())
    print(getattr(self, 'recordings_to_retrain').exists())
    if self.pk!=None and getattr(self, 'recordings_to_retrain').exists():
    	return mark_safe('<a href="/admin/normalization/model/%s/retrain" class="grp-button">Retrain</a>' %(self.pk))
    return '(add recordings to retrain and save to enable retraining)'


class Word(models.Model):
  to_model = models.ForeignKey('Model')
  transcription = models.CharField(max_length=30)
  normalization = models.CharField(max_length=30)
  lemma = models.CharField(max_length=30)
  annotation = models.TextField()
  translation = models.CharField(max_length=50)
  
  class Meta:
    verbose_name_plural = 'Words normalized manually'