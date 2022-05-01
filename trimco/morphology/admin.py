from django.contrib import admin
from morphology.models import *
from reversion.admin import VersionAdmin


@admin.register(Language)
class LanguageAdmin(VersionAdmin):
    pass


@admin.register(Dialect)
class DialectAdmin(VersionAdmin):
    pass


@admin.register(Lemma)
class LemmaAdmin(VersionAdmin):
    pass


@admin.register(Form)
class FormAdmin(VersionAdmin):
    pass


@admin.register(TokenToForm)
class TokenToFormAdmin(VersionAdmin):
    pass


@admin.register(Token)
class TokenAdmin(VersionAdmin):
    pass


@admin.register(GlossingRule)
class GlossingRuleAdmin(VersionAdmin):
    pass
