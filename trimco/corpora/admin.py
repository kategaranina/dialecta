import traceback
import json

from django.contrib import admin

from django.db import transaction
from django.conf.urls import url
from django.template.context import RequestContext
from django.shortcuts import render_to_response, get_object_or_404

from corpora.models import *
from corpora.utils.elan_to_html import ElanToHTML
from corpora.utils.standartizator import Standartizator
from corpora.utils.annotation_menu import annotation_menu
from corpora.utils.word_list import insert_manual_annotation_in_mongo
from corpora.search_engine.search_backend import search, saved_recording_to_db
from corpora.search_engine.db_to_html import html_to_db
from morphology.models import Dialect

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from reversion.admin import VersionAdmin


class HttpResponseConflict(HttpResponse):
    status_code = 409  # Conflict


CONFLICT_RESPONSE = HttpResponseConflict(
    'Another request is currently running. Try to reload the page in several seconds. <br>'
    'If the error persists, please contact developers and describe the problem.'
)


@admin.register(Recording)
class RecordingAdmin(VersionAdmin):

    list_display = ('string_id', 'audio','speakerlist', 'title', 'auto_annotated', 'checked')
    search_fields = ('to_speakers__string_id',)
    list_max_show_all = 500
    list_per_page = 200
    filter_horizontal = ('to_speakers', 'to_interviewers')

    editor_template = 'editor.html'
    search_template = 'search.html'
    fields = (
        'string_id',
        ('audio','data'),
        ('edit_transcription', 'annotate_transcription'),
        ('auto_annotated', 'checked'),
        ('recording_date', 'recording_time', 'recording_place'),
        'file_check',
        ('audio_data', 'participants'),
        'to_speakers',
        'to_interviewers',
        'speakerlist',
        'title',
        'topics',
        'comments',
        'metacomment1',
        ('metacomment2', 'metacomment3'),
        'to_dialect',
        'recording_device',
    )
    readonly_fields = (
        'audio_data',
        'participants',
        'speakerlist',
        'file_check',
        'edit_transcription',
        'annotate_transcription'
    )

    save_as = True

    class Media:
        js = ("js/ustie_id.js", "js/search_button.js", "js/reannotate_all_button.js")
        css = {'all': ("css/search_button.css",)}

    def speakerlist(self, obj):
        return ', '.join([a.string_id for a in obj.to_speakers.all()])

    def get_urls(self):
        self.processing_request = False
        urls = super(RecordingAdmin, self).get_urls()
        my_urls = [
            url(r'\d+/edit/$', self.admin_site.admin_view(self.edit)),
            url(r'\d+/auto/$', self.admin_site.admin_view(self.auto_annotate)),
            url(r'^reannotate_grammar_all/$', self.admin_site.admin_view(self.reannotate_grammar_all_unchecked)),
            url(r'^search/$', self.admin_site.admin_view(self.search)),
            url(r'^ajax/$', self.ajax_dispatcher, name='ajax'),
            url(r'^ajax_search/$', self.ajax_search_dispatcher, name='ajax_search')
        ]
        return my_urls + urls

    @transaction.atomic
    def edit(self, request):
        if self.processing_request:
            return CONFLICT_RESPONSE

        self.processing_request = True

        try:
            self.recording_obj = get_object_or_404(Recording, id=request.path.split('/')[-3])
            self.elan_converter = ElanToHTML(self.recording_obj)
            self.elan_converter.build_page()
            annot_menu_select, annot_menu_checkboxes = annotation_menu.build_annotation_menu()

            self.standartizator = Standartizator(self.recording_obj.to_dialect)

            context = {
                'ctext': self.elan_converter.html,
                'audio_path': self.recording_obj.audio.name,
                'media': self.media['js'],
                'annot_menu_select': annot_menu_select,
                'annot_menu_checkboxes': annot_menu_checkboxes,
                'auto_annotation_option': True
            }

        except Exception:
            self.processing_request = False
            print(traceback.format_exc())
            raise Exception(traceback.format_exc())

        self.processing_request = False
        return render_to_response(self.editor_template, context_instance=RequestContext(request, context))

    @transaction.atomic
    def search(self, request):
        if self.processing_request:
            return CONFLICT_RESPONSE

        self.processing_request = True

        try:
            annot_menu_select, annot_menu_checkboxes = annotation_menu.build_annotation_menu()
            dialects = [(x.id, x.abbreviation) for x in Dialect.objects.all()]

            context = {
                'ctext': '',
                'audio_path': '',
                'media': self.media['js'],
                'annot_menu_select': annot_menu_select,
                'annot_menu_checkboxes': annot_menu_checkboxes,
                'dialects': dialects,
                'auto_annotation_option': False
            }

        except Exception:
            self.processing_request = False
            print(traceback.format_exc())
            raise Exception(traceback.format_exc())

        self.processing_request = False
        return render_to_response(self.search_template, context_instance=RequestContext(request, context))

    @transaction.atomic
    def auto_annotate(self, request):
        if self.processing_request:
            return CONFLICT_RESPONSE

        self.processing_request = True

        try:
            self.recording_obj = get_object_or_404(Recording, id=request.path.split('/')[-3])
            self.elan_converter = ElanToHTML(self.recording_obj, mode='auto-annotation')
            self.elan_converter.build_page()

            annot_menu_select, annot_menu_checkboxes = annotation_menu.build_annotation_menu()

            context = {
                'ctext': self.elan_converter.html,
                'audio_path': self.recording_obj.audio.name,
                'media': self.media['js'],
                'annot_menu_select': annot_menu_select,
                'annot_menu_checkboxes': annot_menu_checkboxes,
                'auto_annotation_option': True
            }

        except Exception:
            self.processing_request = False
            print(traceback.format_exc())
            raise Exception(traceback.format_exc())

        self.processing_request = False
        return render_to_response(self.editor_template, context_instance=RequestContext(request, context))

    def reannotate_grammar_all_unchecked(self, _):
        unchecked_recs = Recording.objects.filter(auto_annotated=True, checked=False)
        reannotated = []

        for rec in unchecked_recs:
            clean_rec = rec.data.path.rsplit('/', 1)[-1]
            elan_converter = ElanToHTML(rec)
            elan_converter.make_backup()

            try:
                elan_converter.reannotate_elan(do_standartization=False)
                elan_converter.change_status_and_save()
                print('Reannotated and saved', rec.data.path)
                reannotated.append(clean_rec)
            except Exception as e:
                reannotated.append(clean_rec + ' ERROR ' + str(e))
                print('ERROR in ' + rec.data.path)
                print(e)

        return HttpResponse('Reannotated:<br>' + '<br>'.join(reannotated))

    @csrf_exempt
    def ajax_dispatcher(self, request):
        if self.processing_request:
            return CONFLICT_RESPONSE

        response = {}
        self.processing_request = True

        try:
            self.recording_obj = get_object_or_404(Recording, id=request.META['HTTP_REFERER'].split('/')[-3])
            self.standartizator = Standartizator(self.recording_obj.to_dialect)

            if request.POST['request_type'] == 'trt_annot_req':
                if request.POST['request_data[mode]'] == 'manual':
                    manual_words = self.standartizator.get_manual_standartizations(request.POST['request_data[trt]'])
                    response['result'] = manual_words or [request.POST['request_data[nrm]']]

                elif request.POST['request_data[mode]'] == 'auto':
                    response['result'] = self.standartizator.get_auto_standartization(request.POST['request_data[trt]'])

            elif request.POST['request_type'] == 'annot_suggest_req':
                ann = [request.POST['request_data[trt]'], request.POST['request_data[nrm]']]
                response['result'] = self.standartizator.get_annotation_options_list(ann)

            elif request.POST['request_type'] == 'save_elan_req':
                self.elan_converter.save_html_to_elan(request.POST['request_data[html]'])
                saved_recording_to_db(
                    eaf_path=self.recording_obj.data.path,
                    audio_path=self.recording_obj.audio.name,
                    html=request.POST['request_data[html]'],
                    dialect=self.recording_obj.to_dialect.id
                )

            elif request.POST['request_type'] == 'save_annotation':
                insert_manual_annotation_in_mongo(
                    model=str(self.standartizator.model),
                    word=request.POST['request_data[trt]'],
                    standartization=request.POST['request_data[nrm]'],
                    lemma=request.POST['request_data[lemma]'],
                    grammar=request.POST['request_data[annot]']
                )

        except Exception:
            self.processing_request = False
            print(traceback.format_exc())
            raise Exception(traceback.format_exc())

        self.processing_request = False
        return HttpResponse(json.dumps(response))

    @csrf_exempt
    def ajax_search_dispatcher(self, request):
        if self.processing_request:
            return CONFLICT_RESPONSE

        response = {}
        self.processing_request = True

        if request.POST['request_type'] == 'search':
            try:
                total_pages = request.POST.get('request_data[total_pages]', '')
                if total_pages == '':
                    total_pages = None

                prev_page_info = request.POST.get('request_data[prev_page_info]', '')
                prev_page_info = json.loads(prev_page_info) if prev_page_info != '' else {}

                response['result'], response['page_info'], response['total_pages'] = search(
                    dialect=request.POST.getlist('request_data[dialect][]', []),
                    transcription=request.POST['request_data[transcription]'],
                    standartization=request.POST['request_data[standartization]'],
                    lemma=request.POST['request_data[lemma]'],
                    annotation=request.POST['request_data[annotations]'],
                    start_page=int(request.POST['request_data[start_page]']),
                    prev_page_info=prev_page_info,
                    total_pages=total_pages
                )
            except Exception:
                self.processing_request = False
                print(traceback.format_exc())
                raise Exception(traceback.format_exc())

            self.processing_request = False
            return HttpResponse(json.dumps(response))

        if request.POST['request_type'] == 'save_elan_req':
            try:
                ElanToHTML.save_html_extracts_to_elans(request.POST['request_data[html]'])
                html_to_db(request.POST['request_data[html]'])
            except Exception:
                self.processing_request = False
                print(traceback.format_exc())
                raise Exception(traceback.format_exc())

            self.processing_request = False
            return HttpResponse(json.dumps(response))

        dialect = request.POST.get('request_data[dialect]', '')
        if not dialect:
            self.processing_request = False
            return HttpResponse(json.dumps(response))

        try:
            current_standartizator = Standartizator(dialect)

            if request.POST['request_type'] == 'trt_annot_req':
                if request.POST['request_data[mode]'] == 'manual':
                    manual_words = current_standartizator.get_manual_standartizations(request.POST['request_data[trt]'])
                    response['result'] = manual_words or [request.POST['request_data[nrm]']]

                elif request.POST['request_data[mode]'] == 'auto':
                    # todo: why standartization here, should be annotation?
                    response['result'] = current_standartizator.get_auto_standartization(request.POST['request_data[trt]'])

            elif request.POST['request_type'] == 'annot_suggest_req':
                ann = [request.POST['request_data[trt]'], request.POST['request_data[nrm]']]
                response['result'] = current_standartizator.get_annotation_options_list(ann)

            elif request.POST['request_type'] == 'save_annotation':
                insert_manual_annotation_in_mongo(
                    model=str(current_standartizator.model),
                    word=request.POST['request_data[trt]'],
                    standartization=request.POST['request_data[nrm]'],
                    lemma=request.POST['request_data[lemma]'],
                    grammar=request.POST['request_data[annot]']
                )

        except Exception:
            self.processing_request = False
            print(traceback.format_exc())
            raise Exception(traceback.format_exc())

        self.processing_request = False
        return HttpResponse(json.dumps(response))


@admin.register(Corpus)
class CorpusAdmin(VersionAdmin):
    pass
