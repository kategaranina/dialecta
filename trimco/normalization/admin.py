from django.contrib import admin
from normalization.models import Word, Model
from reversion.admin import VersionAdmin
from django.conf.urls import url
from django.db import transaction
from django.shortcuts import render_to_response, get_object_or_404
from corpora.utils.elan_tools import ElanToHTML
from corpora.utils.standartizator import Standartizator


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
        my_urls = [url(r'\d+/retrain/$', self.admin_site.admin_view(self.retrain))]
        return my_urls + urls
    
    @transaction.atomic
    def retrain(self, request):
        self.to_dialect = get_object_or_404(Model, id=request.path.split('/')[-3]).to_dialect.all()[0]
        self.recordings = get_object_or_404(Model, id=request.path.split('/')[-3]).recordings_to_retrain.all()
        self.recordings = [rec for rec in self.recordings if rec.checked]

        if self.recordings:
            print('Retraining')
            print(self.recordings)

            self.examples = []
            for rec in self.recordings:
                elan_converter = ElanToHTML(rec)
                self.examples += elan_converter.collect_examples()

            self.standartizator = Standartizator(self.to_dialect)
            self.standartizator.make_backup()
            self.standartizator.rewrite_files(self.examples)
            self.standartizator.retrain_model()
            self.result = 'Retraining done. Check normalizer log to ensure no errors occurred.'  # TODO: parse norm log to see success or error

        else:
            self.result = 'No checked recordings. Add manually checked recordings and try again'

        context = {'result': self.result}
        return render_to_response(self.nrm_template, context=context)
