from django.contrib import admin
from django import forms

from django.db import transaction
from django.conf.urls import include, url
from django.template.context import RequestContext
from django.shortcuts import render_to_response, get_object_or_404

from corpora.models import *
from info.models import *
from corpora.elan_tools import standartizator, elan_to_html

import json
from django_ajax.decorators import ajax
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from reversion.admin import VersionAdmin

##class RenameCheckboxAdminForm(forms.ModelForm):
##    # custom field not backed by database
##    rename_files_accordingly = forms.BooleanField(initial=False,required=False)
##
##    # REPLACE WITH BUTTON
##    # CONFIRMATION DIALOG
##    # WRITE TO ELAN
##    # CHECK IF SUCH A FILENAME EXISTS
##
##    class Meta:
##        model = Recording
##        fields = "__all__"

@admin.register(Recording)
class RecordingAdmin(VersionAdmin):

  list_display = ('string_id', 'audio','speakerlist', 'title', 'auto_annotated', 'checked')
  search_fields = ('to_speakers__string_id',)
  list_max_show_all = 500
  list_per_page = 200
  filter_horizontal = ('to_speakers', 'to_interviewers')

  editor_template = 'editor.html'
  trainer_template = 'trainer.html'
  fields = (
            ('string_id'),
            ('audio','data'),
            ('edit_transcription', 'annotate_transcription'),
            ('auto_annotated', 'checked'),
            ('recording_date', 'recording_time', 'recording_place'),
            ('file_check'),
            ('audio_data', 'participants'),
            ('to_speakers'),
            ('to_interviewers'),
            ('speakerlist'),
            ('title'),
            ('topics'),
            ('comments'),
            ('metacomment1'),
            ('metacomment2', 'metacomment3'),
            ('to_dialect'),
            ('recording_device'),
            )
  readonly_fields = ('audio_data','participants','speakerlist','file_check','edit_transcription', 'annotate_transcription')

##  form = RenameCheckboxAdminForm
  save_as=True

  class Media:
    js = ("js/ustie_id.js",)

  def speakerlist(self, obj):
    return ', '.join([a.string_id for a in obj.to_speakers.all()])
	
  def get_urls(self):

    self.processing_request = False
        
    urls = super(RecordingAdmin, self).get_urls()
    my_urls = [url(r'\d+/edit/$', self.admin_site.admin_view(self.edit)),
               url(r'\d+/auto/$', self.admin_site.admin_view(self.auto_annotate)),
               url(r'\d+/train/$', self.admin_site.admin_view(self.train)),
               url(r'^ajax/$', self.ajax_dispatcher, name='ajax'),
               ]
    return my_urls + urls

##  def get_model_object(self, url_pk):
##
##    try:
##      int(url_pk)
##      return Recording.objects.get(pk=url_pk)
##    except ValueError:
##      return None
##
##  def get_alphabetic_number(self, n):
##
##    abc_lst = list(map(chr, range(97, 123)))
##    if n < len(abc_lst): # i.e. n < 26
##      return abc_lst[n]
##    else: #will work only when the number is between 26 and 676
##      n1 = int(n/26)
##      n2 = int((n/26 - n1)*26)
##      return (abc_lst[n1]+abc_lst[n2])
##
##  @transaction.atomic
##  def get_valid_string_id(self, request, index=''):
##
##    model_obj = self.get_model_object(request.POST['modelID'])
##    date_str = request.POST['request_data[date]']
##    speaker_str = request.POST['request_data[speaker]']
##    if index == '':
##      index = 0
##
##    similar_id_queryset = Recording.objects.all().filter(string_id__contains=date_str)
##    if model_obj!=None and index==0:
##      similar_id_queryset = similar_id_queryset.exclude(pk=model_obj.pk)
##      abc_number = model_obj.string_id.split('_')[1]
##    else:
##      abc_number = self.get_alphabetic_number(len(similar_id_queryset)+index)
##      
##    if not list(similar_id_queryset.filter(string_id__contains='_%s_' %(abc_number))):
##      return '%s_%s_%s' %(date_str, abc_number, speaker_str)
##    else:
##      print(list(similar_id_queryset.filter(string_id__contains='_%s_' %(abc_number))))
##      self.get_valid_string_id(request, index+1)
  
  @transaction.atomic
  def edit(self, request):

    self.recording_obj = get_object_or_404(Recording, id=request.path.split('/')[-3])
    self.elan_converter = elan_to_html(self.recording_obj) #, mode='auto-annotation')
    self.elan_converter.build_page()

    #print(self.recording_obj.model_to_normalize)
    #self.annotation = Standartizator(self.recording_obj.model_to_normalize)
    
    self.standartizator = standartizator(self.recording_obj.to_dialect)
    self.standartizator.start_standartizator()

    annot_menu_select, annot_menu_checkboxes = self.elan_converter.build_annotation_menu()
    
    context = {'ctext': self.elan_converter.html,
               'audio_path': self.recording_obj.audio.name,
               'media': self.media['js'],
               'annot_menu_select' : annot_menu_select,
               'annot_menu_checkboxes' : annot_menu_checkboxes,
               }
    return render_to_response(self.editor_template, context_instance=RequestContext(request, context))

  @transaction.atomic
  def auto_annotate(self, request):

    self.recording_obj = get_object_or_404(Recording, id=request.path.split('/')[-3])
    self.elan_converter = elan_to_html(self.recording_obj, mode='auto-annotation')
    self.elan_converter.build_page()

    annot_menu_select, annot_menu_checkboxes = self.elan_converter.build_annotation_menu()

    annot_menu_select, annot_menu_checkboxes = self.elan_converter.build_annotation_menu()
    
    context = {'ctext': self.elan_converter.html,
               'audio_path': self.recording_obj.audio.name,
               'media': self.media['js'],
               'annot_menu_select' : annot_menu_select,
               'annot_menu_checkboxes' : annot_menu_checkboxes,
               }
    return render_to_response(self.editor_template, context_instance=RequestContext(request, context))


  @transaction.atomic
  def train(self, request):

    self.recording_obj = get_object_or_404(Recording, id=request.path.split('/')[-3])
    self.elan_converter = elan_to_html(self.recording_obj, 'orth_trainig')
    
    self.standartizator = standartizator(self.recording_obj.to_dialect)
    self.standartizator.start_standartizator()
    
    context = {'ctext': self.elan_converter.html,
               'audio_path': self.recording_obj.audio.name,
               'media': self.media['js'],
               'examples_dict': json.dumps(self.standartizator.examples_dict),
               'exceptions_lst': json.dumps(self.standartizator.exceptions_lst),
               }
    return render_to_response(self.trainer_template, context_instance=RequestContext(request, context))

  @csrf_exempt
  def ajax_dispatcher(self, request):
      #print(request.POST)
      response = {}
      #if request.POST == {} or self.processing_request == True:
      #  return HttpResponse(json.dumps(response))
      self.processing_request = True
      if request.POST['request_type'] == 'save_model_req':
        self.standartizator.update_model(json.loads(request.POST['request_data[trd]']),
                                         json.loads(request.POST['request_data[exr]']),
                                         )
      elif request.POST['request_type'] == 'training_data_load_req':
        response['training_dict'] = self.standartizator.examples_dict
        #response['exceptions_arr'] = self.standartizator.exceptions_lst
      elif request.POST['request_type'] == 'trt_annot_req':
        #print(request.POST)
        if request.POST['request_data[mode]'] == 'manual':
          response['result'] = self.standartizator.generate_dict_for_translit_token(request.POST['request_data[trt]'])
        elif request.POST['request_data[mode]'] == 'auto':
          response['result'] = self.standartizator.auto_annotation(request.POST['request_data[trt]'])
      elif request.POST['request_type'] == 'annot_suggest_req':
        response['result'] = self.standartizator.get_annotation_options_list(request.POST['request_data[nrm]'])
      elif request.POST['request_type'] == 'save_elan_req':
        self.elan_converter.save_html_to_elan(request.POST['request_data[html]'])
##      elif request.POST['request_type'] == 'string_id_update':
##        response['result'] = self.get_valid_string_id(request)
      #self.processing_request = False
      return HttpResponse(json.dumps(response))


@admin.register(Corpus)
class CorpusAdmin(VersionAdmin):
  pass

