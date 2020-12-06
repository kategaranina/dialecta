from django.contrib import admin
from normalization.models import *
from reversion.admin import VersionAdmin
from django.conf.urls import url
from django.db import transaction
from django.shortcuts import render_to_response, get_object_or_404
from corpora.utils.elan_tools import elan_to_html, Standartizator


#from django.template.context import RequestContext


class WordTableInline(admin.TabularInline):
  model = Word
  ordering = ('transcription',)
  extra = 1
  verbose_name = 'Word'
  verbose_name_plural = 'Words normalized manually'


@admin.register(Model)
class ModelAdmin(VersionAdmin):

  filter_horizontal = ('recordings_to_retrain', 'to_dialect')

  readonly_fields = ('retrain_model',)

  inlines = (WordTableInline,)

  nrm_template = 'nrm.html'

  def get_urls(self):

    self.processing_request = False
        
    urls = super(ModelAdmin, self).get_urls()
    my_urls = [url(r'\d+/retrain/$', self.admin_site.admin_view(self.retrain)),
               ]
    return my_urls + urls
  
  @transaction.atomic
  def retrain(self, request):

    self.to_dialect = get_object_or_404(Model, id=request.path.split('/')[-3]).to_dialect.all()[0]
    self.recordings = get_object_or_404(Model, id=request.path.split('/')[-3]).recordings_to_retrain.all()
    print('Retraining')
    print(self.recordings)
    self.recordings = [rec for rec in self.recordings if rec.checked]
    self.examples = []
    if not self.recordings:
    	self.result = 'No checked recordings. Add manually checked recordings and try again'
    else:
    	for rec in self.recordings:
    		elan_converter = elan_to_html(rec)
    		self.examples += elan_converter.collect_examples()
    	self.result = 'Retraining done'


    self.standartizator = Standartizator(self.to_dialect)
    self.standartizator.make_backup()
    self.standartizator.rewrite_files(self.examples)
    self.standartizator.retrain_model()

    context = {'result': self.result}

    #return render_to_response(self.nrm_template, context_instance=RequestContext(request, context))
    return render_to_response(self.nrm_template, context=context)