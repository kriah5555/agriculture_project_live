"""
App-wide translatable strings.

  Language           a UI language (en/kn/hi …). New languages are rows, not code.
  TranslationString  one translatable text, keyed by "<module>.<name>" (e.g.
                     "report.title"); `module` is the key's first segment.
  Translation        the text of a string in one language (English included).
"""
from django.conf import settings
from django.db import models


class Language(models.Model):
    code        = models.CharField(max_length=10, unique=True, help_text='e.g. en, kn, hi')
    name        = models.CharField(max_length=60, help_text='English name, e.g. Kannada')
    native_name = models.CharField(max_length=60, help_text='e.g. ಕನ್ನಡ')
    font_family = models.CharField(max_length=200, blank=True, default='',
                                   help_text="CSS font family for this script, e.g. 'Noto Sans Kannada'")
    is_active   = models.BooleanField(default=True)
    is_default  = models.BooleanField(default=False)
    sort_order  = models.PositiveSmallIntegerField(default=0)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.native_name} ({self.code})'

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().lower()
        super().save(*args, **kwargs)
        if self.is_default:   # exactly one default
            Language.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)


def module_of(key):
    return (key or '').split('.', 1)[0][:50]


class TranslationString(models.Model):
    key        = models.CharField(max_length=150, unique=True)
    module     = models.CharField(max_length=50, db_index=True, editable=False)
    context    = models.CharField(max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key

    def save(self, *args, **kwargs):
        self.module = module_of(self.key)
        super().save(*args, **kwargs)


class Translation(models.Model):
    string   = models.ForeignKey(TranslationString, on_delete=models.CASCADE, related_name='translations')
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='translations')
    text     = models.TextField(blank=True, default='')
    reviewed = models.BooleanField(default=False,
                                   help_text='Checked by a native speaker (machine drafts start unreviewed).')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['string', 'language'], name='uniq_translation_per_language')]

    def __str__(self):
        return f'{self.string.key} [{self.language.code}]'
