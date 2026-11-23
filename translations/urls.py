from django.urls import path
from . import views

urlpatterns = [
    path('',                 views.index,         name='translations'),
    path('save/',            views.save,          name='translations-save'),
    path('reset/',           views.reset,         name='translations-reset'),
    path('export.csv',       views.export_csv,    name='translations-export'),
    path('import/',          views.import_csv,    name='translations-import'),
    path('languages/save/',  views.language_save, name='translations-language-save'),
]
