from django.db import models
from morphology.models import Dialect
from corpora.models import Recording
#from morphology.models import *


class Model(models.Model):

  name = models.CharField(max_length=10) #!this should correspond to the actual folder name of the model inside csmtiser normalizer !
  to_dialect = models.ForeignKey(Dialect, blank=True, null=True,
                                      verbose_name='Dialect')
  recordings_to_retrain = models.ManyToManyField(Recording, blank=True)

  def __str__(self):
    return self.name