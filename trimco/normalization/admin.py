from django.contrib import admin
from normalization.models import *
from reversion.admin import VersionAdmin


@admin.register(Model)
class ModelAdmin(VersionAdmin):

  filter_horizontal = ('recordings_to_retrain', )

# Register your models here.
