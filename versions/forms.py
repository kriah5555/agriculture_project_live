from django import forms
from .models import AppVersion

class AppVersionForm(forms.ModelForm):
    class Meta:
        model = AppVersion
        fields = '__all__'

    def clean_zip_file(self):
        zip_file = self.cleaned_data.get('zip_file')
        if zip_file:
            if not zip_file.name.lower().endswith('.zip'):
                raise forms.ValidationError("Only ZIP files are allowed.")
        return zip_file

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
