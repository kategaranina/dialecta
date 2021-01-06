from django.template.context import RequestContext
from django.shortcuts import render_to_response

from corpora.utils.annotation_menu import AnnotationMenuFromXML
from corpora.models import Recording
from info.models import Location, Speaker
from morphology.models import Language, Dialect


a = AnnotationMenuFromXML('grammemes_pymorphy2.xml')


def queries(request):
    context = {
        'language': get_choices('language', [(l.name, l.pk) for l in Language.objects.all()]),
        'dialect': get_choices('dialect', [(d.name, d.pk) for d in Dialect.objects.all()]),
        'location': get_choices('location', [(l.name, l.pk) for l in Location.objects.all()]),
        'speaker': get_choices('speaker', [(s.__str__(), s.pk) for s in Speaker.objects.all()]),
        'recording': get_choices('recording', [(r.__str__(), r.pk) for r in Recording.objects.all()]),
        'annot_menu_1': a.menu_html_str_1,
        'annot_menu_2': a.menu_html_str_2,
    }
    return render_to_response('queries.html', context_instance=RequestContext(request, context))


def get_choices(choices_id, choices_lst):
    choices_tag_str = ''
    for ID, value in choices_lst:
        choices_tag_str += '<option value="%s">%s</option>' % (value, ID)
    return '<select id="%s">%s</select>' % (choices_id, choices_tag_str)
