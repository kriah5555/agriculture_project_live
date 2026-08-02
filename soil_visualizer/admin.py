from django.contrib import admin

from agriapp.models import Plot, Point


@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display  = ('name', 'devise', 'created_at', 'updated_at')
    list_filter   = ('devise',)
    search_fields = ('name', 'devise__name')


@admin.register(Point)
class PointAdmin(admin.ModelAdmin):
    list_display  = ('id', 'devise', 'plot', 'reading', 'coordinates', 'sample_date')
    list_filter   = ('devise', 'plot')
    search_fields = ('notes',)
