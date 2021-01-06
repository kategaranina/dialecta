from django.contrib import admin
from info.models import *
from reversion.admin import VersionAdmin


class PersonalRelationInline(admin.TabularInline):
    model = PersonalRelation
    extra = 0
    fk_name = 'from_speaker'
    verbose_name_plural = 'Relations to other speakers'
    
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        """
        Overriding to_speaker field choices to avoid recursive relations
        """
        field = super(PersonalRelationInline, self).formfield_for_foreignkey(db_field, request, **kwargs)     
        speaker_id = request.path_info.split('/')[-3]

        try:
            speaker_id = int(speaker_id)
            if db_field.name == 'to_speaker' and speaker_id != 'add':
                field.queryset = field.queryset.exclude(pk=speaker_id)
        except ValueError:
            pass

        return field


class LocationRelationInline(admin.TabularInline):
    model = LocationRelation
    extra = 1
    verbose_name = 'Location'
    verbose_name_plural = 'Geography of Life'


class LanguageRelationInline(admin.TabularInline):
    model = LanguageRelation
    extra = 1
    verbose_name = 'Language'
    verbose_name_plural = 'Linguistic Repertoire'


@admin.register(Speaker)
class SpeakerAdmin(VersionAdmin):
    list_display = ('last_name', 'first_name', 'patronimic_name', 'sex', 'year_of_birth', 'education')
    search_fields = ('last_name', 'first_name')
    readonly_fields = ['place_of_birth']
    inlines = (PersonalRelationInline, LocationRelationInline, LanguageRelationInline)
    fieldsets = (
        (
            'Basic info',
            {
                'fields': (
                    ('string_id', 'sex', 'year_of_birth'),
                    ('last_name', 'first_name'),
                    ('patronimic_name', 'other_names'),
                    ('pob', 'por', 'pofr'),
                )
            }
        ),
        (
            'Education and profession',
            {
                'fields': (
                    ('education', 'education_text'),
                    ('profession', 'mobility')
                )
            }
        ),
        (
            'Place of birth',
            {
                'fields': ('place_of_birth',)
            }
         ),
        (
            'Geography of Life',
            {
                'classes': ('placeholder locationrelation_set-group',),
                'fields': (),
            }
        ),
        (
            'Other', {
                'fields': ('details',)
            }
        ),
        (
            'Linguistic Biography',
            {
                'classes': ('placeholder languagerelation_set-group',),
                'fields': ()
            }
        ),
        (
            'Relations with other speakers', {
                'classes': ('placeholder personalrelation_set-group',),
                'fields': ()
            }
        )
    )


@admin.register(Location)
class LocationAdmin(VersionAdmin):
    pass


@admin.register(RelationType)
class RelationTypeAdmin(VersionAdmin):
    pass


@admin.register(EducationType)
class EducationTypeAdmin(VersionAdmin):
    pass


@admin.register(Interviewer)
class EducationInterviewerAdmin(VersionAdmin):
    pass
