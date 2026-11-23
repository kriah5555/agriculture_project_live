"""Admin editor for app-wide translations (navbar → Languages, /translations/)."""
import csv
import io
import json

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from agriapp.views import admin_required

from . import api
from .models import Language, Translation, TranslationString, module_of
from .seeding import seed_default

PAGE_SIZE = 40
PREVIEW_URLS = {  # module -> preview link template ({lang} filled in)
    'report': '/soil-report/?api_id={api_id}&lang={lang}',
}


def _languages():
    return list(Language.objects.all())


@admin_required
@require_GET
def index(request):
    languages = _languages()
    active = [l for l in languages if l.is_active]
    module = request.GET.get('module', '')
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')          # '', 'missing', 'review'
    status_lang = request.GET.get('slang', '')      # language the status filter applies to

    qs = TranslationString.objects.all()
    if module:
        qs = qs.filter(module=module)
    if q:
        qs = qs.filter(Q(key__icontains=q) | Q(context__icontains=q) | Q(translations__text__icontains=q)).distinct()

    check_langs = [l for l in active if not status_lang or l.code == status_lang]
    if status == 'missing':
        cond = Q()
        for l in check_langs:
            cond |= ~Q(pk__in=Translation.objects.filter(language=l).exclude(text='').values('string_id'))
        qs = qs.filter(cond)
    elif status == 'review':
        cond = Q()
        for l in check_langs:
            if not l.is_default:
                cond |= Q(translations__language=l, translations__reviewed=False)
        qs = qs.filter(cond).distinct() if cond else qs.none()

    page = Paginator(qs.order_by('key'), PAGE_SIZE).get_page(request.GET.get('page'))
    ids = [s.pk for s in page.object_list]
    by_string = {}
    for tr in Translation.objects.filter(string_id__in=ids).select_related('language'):
        by_string.setdefault(tr.string_id, {})[tr.language.code] = tr
    rows = [{'s': s, 'cells': [(l, by_string.get(s.pk, {}).get(l.code)) for l in active]} for s in page.object_list]

    totals = TranslationString.objects.count()
    lang_stats = []
    for l in active:
        done = Translation.objects.filter(language=l).exclude(text='').count()
        reviewed = Translation.objects.filter(language=l, reviewed=True).exclude(text='').count()
        lang_stats.append({'lang': l, 'done': done, 'reviewed': reviewed,
                           'pct': round(done / totals * 100) if totals else 0,
                           'rpct': round(reviewed / totals * 100) if totals else 0,
                           'dpct': max(0, (round(done / totals * 100) if totals else 0) - (round(reviewed / totals * 100) if totals else 0))})

    params = request.GET.copy(); params.pop('page', None)
    from agriapp.models import DeviseApis
    sample = DeviseApis.objects.filter(device__devise_type='soilsaathi').order_by('-id').values_list('id', flat=True).first()
    return render(request, 'translations/index.html', {
        'active_page': 'translations',
        'languages': languages, 'active_langs': active, 'rows': rows, 'page': page,
        'modules': list(TranslationString.objects.values('module').annotate(n=Count('id')).order_by('module')),
        'module': module, 'q': q, 'status': status, 'slang': status_lang,
        'qs_no_page': params.urlencode(), 'total_strings': totals, 'lang_stats': lang_stats,
        'preview_api_id': request.GET.get('api_id') or sample or '',
        'preview_urls_json': json.dumps(PREVIEW_URLS),
    })


@admin_required
@require_POST
def save(request):
    """Save one cell: string_id, lang, text, reviewed (optional)."""
    s = get_object_or_404(TranslationString, pk=request.POST.get('string_id'))
    lang = get_object_or_404(Language, code=request.POST.get('lang'))
    tr, _ = Translation.objects.get_or_create(string=s, language=lang)
    if 'text' in request.POST:
        tr.text = request.POST['text'].replace('\r\n', '\n')
    if 'reviewed' in request.POST:
        tr.reviewed = request.POST['reviewed'] in ('1', 'true', 'on')
    tr.save()
    s.updated_by = request.user if request.user.is_authenticated else None
    s.save(update_fields=['updated_by', 'updated_at', 'module'])
    return JsonResponse({'ok': True, 'text': tr.text, 'reviewed': tr.reviewed,
                         'updated': timezone.localtime(s.updated_at).strftime('%Y-%m-%d %H:%M')})


@admin_required
@require_POST
def reset(request):
    """Restore one cell to its seeded default text."""
    s = get_object_or_404(TranslationString, pk=request.POST.get('string_id'))
    lang = get_object_or_404(Language, code=request.POST.get('lang'))
    default = seed_default(s.key, lang.code)
    if default is None:
        return JsonResponse({'ok': False, 'error': 'No default text for this language.'}, status=404)
    tr, _ = Translation.objects.get_or_create(string=s, language=lang)
    tr.text, tr.reviewed = default, lang.is_default
    tr.save()
    s.updated_by = request.user if request.user.is_authenticated else None
    s.save(update_fields=['updated_by', 'updated_at', 'module'])
    return JsonResponse({'ok': True, 'text': tr.text, 'reviewed': tr.reviewed})


@admin_required
@require_GET
def export_csv(request):
    languages = _languages()
    module = request.GET.get('module', '')
    qs = TranslationString.objects.order_by('key').prefetch_related('translations__language')
    if module:
        qs = qs.filter(module=module)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['key', 'module', 'context'] + [l.code for l in languages] + [f'{l.code}_reviewed' for l in languages])
    for s in qs:
        trs = {t.language.code: t for t in s.translations.all()}
        w.writerow([s.key, s.module, s.context]
                   + [trs[l.code].text if l.code in trs else '' for l in languages]
                   + [('1' if trs[l.code].reviewed else '0') if l.code in trs else '' for l in languages])
    resp = HttpResponse('﻿' + buf.getvalue(), content_type='text/csv; charset=utf-8')   # BOM so Excel reads UTF-8
    resp['Content-Disposition'] = f'attachment; filename="translations_{module or "all"}_{timezone.now():%Y%m%d}.csv"'
    return resp


@admin_required
@require_POST
def import_csv(request):
    """Upsert by key. Columns: key, [module], [context], <lang codes…>, [<code>_reviewed…].
    Blank cells leave existing text untouched."""
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'ok': False, 'error': 'Choose a CSV file.'}, status=400)
    try:
        text = f.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return JsonResponse({'ok': False, 'error': 'The file must be UTF-8 encoded CSV.'}, status=400)
    reader = csv.DictReader(io.StringIO(text))
    cols = reader.fieldnames or []
    if 'key' not in cols:
        return JsonResponse({'ok': False, 'error': 'Missing required "key" column.'}, status=400)
    langs = {l.code: l for l in _languages()}
    lang_cols = [c for c in cols if c in langs]
    if not lang_cols:
        return JsonResponse({'ok': False, 'error': f'No language columns found (expected one of: {", ".join(langs)}).'}, status=400)
    created = updated = 0
    errors = []
    with transaction.atomic():
        for n, row in enumerate(reader, start=2):
            key = (row.get('key') or '').strip()
            if not key or '.' not in key:
                errors.append(f'Row {n}: key must look like "module.name".')
                continue
            s, made = TranslationString.objects.get_or_create(key=key, defaults={'context': (row.get('context') or '')[:255]})
            created += made
            if not made and row.get('context'):
                s.context = row['context'][:255]
            for code in lang_cols:
                val = (row.get(code) or '').replace('\r\n', '\n')
                rv = (row.get(f'{code}_reviewed') or '').strip()
                if not val.strip() and not rv:
                    continue
                tr, _ = Translation.objects.get_or_create(string=s, language=langs[code])
                changed = False
                if val.strip() and val != tr.text:
                    tr.text, changed = val, True
                if rv in ('0', '1') and (rv == '1') != tr.reviewed:
                    tr.reviewed, changed = rv == '1', True
                if changed:
                    tr.save(); updated += 1
            s.updated_by = request.user if request.user.is_authenticated else None
            s.save()
    api.invalidate()
    return JsonResponse({'ok': True, 'created': created, 'updated': updated, 'errors': errors[:20]})


@admin_required
@require_POST
def language_save(request):
    """Add or update a language (code, name, native_name, font_family, is_active, is_default, sort_order)."""
    code = (request.POST.get('code') or '').strip().lower()
    if not code or not code.replace('-', '').isalnum() or len(code) > 10:
        return HttpResponseBadRequest('Invalid language code.')
    lang, _ = Language.objects.get_or_create(code=code, defaults={'name': code, 'native_name': code})
    for field in ('name', 'native_name', 'font_family'):
        if request.POST.get(field) is not None:
            setattr(lang, field, request.POST[field].strip()[:200])
    if request.POST.get('sort_order', '').isdigit():
        lang.sort_order = int(request.POST['sort_order'])
    lang.is_active = request.POST.get('is_active') == 'on' or lang.is_default
    if request.POST.get('is_default') == 'on':
        lang.is_default, lang.is_active = True, True
    lang.save()
    return redirect(f"{request.POST.get('next') or '/translations/'}#languages")
