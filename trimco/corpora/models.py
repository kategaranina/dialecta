from django.db import models
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os
import sndhdr
from info.models import Location, Speaker, Interviewer
from morphology.models import Dialect
from django.utils import timezone
from django.utils.safestring import mark_safe
from corpora.utils.elan_utils import ElanObject


class OverwriteStorage(FileSystemStorage):
    """
    Overwrite media files when an old one with the same name exists
    """
    def get_available_name(self, name):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


class Recording(models.Model):
    # for import from google docs: filename WITHOUT mp3 or wav
    string_id = models.CharField(max_length=30, verbose_name='Unique ID', unique=True)  # C
    recording_date = models.DateField(default=timezone.now)  # COMPUTED FROM FILENAME
    recording_time = models.TimeField(blank=True, null=True)
    recording_place = models.ForeignKey(Location, blank=True, null=True)

    # TODO: should be changed to "transcription"
    data = models.FileField(storage=OverwriteStorage(), blank=True,null=True, verbose_name='Transcription')  # look into directory!
    audio = models.FileField(storage=OverwriteStorage(), blank=True, null=True)  # look into directory!

    # ONLY for import from google docs: metacomment1, metacomment2, metacomment3 from the Google docs columns A, B and D
    metacomment1 = models.CharField(max_length=100, blank=True, verbose_name='MetaComment1')  # A
    metacomment2 = models.CharField(max_length=100, blank=True, verbose_name='MetaComment2')  # B
    metacomment3 = models.CharField(max_length=100, blank=True, verbose_name='MetaComment3')  # D

    title = models.CharField(blank=True, max_length=100)  # G
    topics = models.TextField(blank=True)  # H
    comments = models.TextField(blank=True)  # I
    
    # ONLY for import from google docs: "participants", "informant"
    participants_field = models.TextField(verbose_name='OF: participants', blank=True)  # I
    informant = models.TextField(verbose_name='OF: informant', blank=True)  # T

    location = models.TextField(verbose_name='Location')  # U

    recording_device = models.CharField(max_length=60, blank=True)  # V
    to_dialect = models.ForeignKey(Dialect, blank=True, null=True, verbose_name='Dialect')
    to_speakers = models.ManyToManyField(Speaker, blank=True, verbose_name='Speakers')  # THESE TO BE CONSTRUCTED FROM INF1..INF4
    to_interviewers = models.ManyToManyField(Interviewer, blank=True, verbose_name='Interviewers')  # not used right now
    checked = models.BooleanField(verbose_name='Manually checked', default=False)

    auto_annotated = models.BooleanField(verbose_name='Automatically annotated', default=False)

    def __str__(self):
        return '{}: {status}checked'.format(self.string_id, status='' if self.checked else 'not ')

    def participants(self):
        if self.data.path:
            try:
                elan_obj = ElanObject(self.data.path)
                return ', '.join(elan_obj.participants_lst)
            except FileNotFoundError:
                pass
        return ''

    def rename_data_file(self, new_name):
        path, old_name = os.path.split(self.data.path)
        new_name = os.path.join(path, '%s.%s' % (new_name, old_name.split('.')[1]))
        os.rename(self.data.path, new_name)
        self.data.name = new_name
        self.save()

    def rename_audio_file(self, new_name):
        path, old_name = os.path.split(self.audio.path)
        new_name = os.path.join(path, '%s.%s' % (new_name, old_name.split('.')[1]))
        os.rename(self.audio.path, new_name)
        self.audio.name = new_name
        self.save()

    def audio_data(self):
        if self.audio.path:
            try:
                data = sndhdr.what(self.audio.path)
                data_str = 'filetype: %s, framerate: %s, nchannels: %s, nframes: %s, sampwidth: %s' % (
                    data[0], data[1], data[2], data[3], data[4]
                )
                return data_str
            except:
                pass
        return 'None'

    def edit_transcription(self):
        if self.pk is not None and self.data is not None:
            return mark_safe('<a href="/admin/corpora/recording/%s/edit" class="grp-button">Edit</a>' % self.pk)
        return '(add transcription data and save to enable editing)'

    def annotate_grammar(self):
        if self.pk is not None and self.data is not None:
            return mark_safe('<a href="/admin/corpora/recording/%s/grammar" class="grp-button">Auto annotate grammar</a>' % self.pk)
        return '(add transcription data and save to enable automatic grammar annotation)'

    def annotate_transcription(self):
        if self.pk is not None and self.data is not None:
            return mark_safe('<a href="/admin/corpora/recording/%s/auto" class="grp-button">Auto normalize and annotate grammar</a>' % self.pk)
        return '(add transcription data and save to enable automatic annotation)'

    def file_check(self): 
        if self.string_id is None:
            return ''

        matching_files_lst = []
        for root, dirs, files in os.walk(settings.MEDIA_ROOT):
            for file in files:
                if file.startswith(self.string_id + '.'):
                    matching_files_lst.append(file)

        return ', '.join(matching_files_lst)
        
    class Meta:
        verbose_name = 'Recording'
        verbose_name_plural = 'Recordings'


class Corpus(models.Model):
    to_files = models.ManyToManyField(Recording, verbose_name='Elan data')

    class Meta:
        verbose_name_plural = 'Corpora'
