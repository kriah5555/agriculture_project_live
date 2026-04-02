from django import forms
from .models import AppVersion

class AppVersionForm(forms.ModelForm):
    class Meta:
        model = AppVersion
        fields = '__all__'

    ALLOWED_EXTENSIONS = ('.zip', '.apk', '.rar', '.tar.gz')

    def clean_zip_file(self):
        upload = self.cleaned_data.get('zip_file')
        if upload and hasattr(upload, 'name'):
            name = upload.name.lower()
            if not any(name.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
                raise forms.ValidationError(
                    "Unsupported file type. Allowed: .zip, .apk, .rar, .tar.gz"
                )
        return upload

    def clean(self):
        cleaned_data = super().clean()
        is_active = cleaned_data.get('is_active')

        if is_active:
            qs = AppVersion.objects.filter(is_active=True)
            # exclude current object during update
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "Only one app version can be active at a time."
                )

        return cleaned_data
