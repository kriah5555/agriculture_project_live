"""
Soil Visualizer mobile API — draw & save field-plot boundaries (GeoJSON
polygons) against a SoiLENZ reading, and fetch them back to display on the
mobile map.

A reading can have more than one plot (matching the admin-only
soil_visualizer dashboard, which already allows drawing several boundaries
for the same reading) — POST always adds a new plot, GET returns every plot
linked to the reading so the mobile map can render all of them, same as the
web UI's embedded map does.

Uses the same Plot/Point models (agriapp.models) as the admin dashboard — a
plot saved here shows up there too, and vice versa.

Routes (mounted under /api/mobile/devices/<id>/soilsaathi/<call_id>/):
  GET  /plots/    List every plot boundary saved for this reading
  POST /plots/    Add a new plot boundary for this reading
"""
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiResponse

from agriapp.models import Devise, DeviseApis, Plot, Point
from devise_apis.mobile_serializers import (
    SoilVisualizerPlotSerializer,
    SoilVisualizerPlotCreateSerializer,
)


def _get_soilenz_device(request, device_id):
    return get_object_or_404(Devise, pk=device_id, user=request.user, devise_type='soilsaathi')


@extend_schema(
    tags=['Soil Visualizer'],
    summary="List or add plot boundaries for a reading",
    description=(
        "GET returns every plot boundary saved for this reading — GeoJSON "
        "geometry, centroid coordinates and sample points for each — so the "
        "mobile map can render all of them, not just the latest.\n\n"
        "POST adds a new plot boundary for this reading; a reading can have "
        "more than one."
    ),
    request=SoilVisualizerPlotCreateSerializer,
    responses={
        200: SoilVisualizerPlotSerializer(many=True),
        201: SoilVisualizerPlotSerializer,
        400: OpenApiResponse(description='Validation error (POST only)'),
    },
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def soilsaathi_plots(request, device_id, call_id):
    device  = _get_soilenz_device(request, device_id)
    reading = get_object_or_404(DeviseApis, pk=call_id, device=device)

    if request.method == 'GET':
        plots = Plot.objects.filter(devise=device, points__reading=reading).distinct()
        return Response(SoilVisualizerPlotSerializer(plots, many=True).data)

    name     = (request.data.get('name') or '').strip() or (reading.area_name or f'Plot for reading #{reading.pk}')
    geometry = request.data.get('geometry')
    serializer = SoilVisualizerPlotCreateSerializer(data={'name': name, 'geometry': geometry})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    plot = serializer.save(devise=device)
    Point.objects.create(
        devise=device, plot=plot, reading=reading,
        coordinates=({'lat': reading.latitude, 'lon': reading.longitude}
                     if reading.latitude and reading.longitude else None),
        sample_date=reading.created_at.date(),
    )
    return Response(SoilVisualizerPlotSerializer(plot).data, status=status.HTTP_201_CREATED)
