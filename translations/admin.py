from django.contrib import admin

from .models import Language, Translation, TranslationString


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'native_name', 'font_family', 'is_active', 'is_default', 'sort_order')
    list_editable = ('is_active', 'sort_order')


class TranslationInline(admin.TabularInline):
    model = Translation
    extra = 0


@admin.register(TranslationString)
class TranslationStringAdmin(admin.ModelAdmin):
    list_display = ('key', 'module', 'context', 'updated_at')
    list_filter = ('module',)
    search_fields = ('key', 'context', 'translations__text')
    inlines = [TranslationInline]
