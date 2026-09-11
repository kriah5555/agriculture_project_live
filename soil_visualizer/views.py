import json

import numpy as np
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin

from agriapp.models import Devise, DeviseApis, Plot, Point
from agriapp.views import admin_required

from .interpolation import IDWInterpolator, SingleSampleGradientInterpolator, PARAMETER_DEFAULTS


def _get_soilenz_devise(device_id):
    return get_object_or_404(Devise, pk=device_id, devise_type='soilsaathi')


def _point_json(point):
    return {
        'id': point.id,
        'plot': point.plot_id,
        'plot_name': point.plot.name if point.plot_id else None,
        'reading_id': point.reading_id,
        'coordinates': point.coordinates,
        'parameters': point.get_parameters(),
        'sample_date': point.sample_date.isoformat(),
        'notes': point.notes,
    }


@admin_required
@xframe_options_sameorigin
def dashboard_view(request, device_id):
    # Allow same-origin framing — this page is now embedded inline (via iframe)
    # on the SoiLENZ/PHBottle/AtmosSense reading-detail pages, not just linked to.
    devise = _get_soilenz_devise(device_id)
    return render(request, 'soil_visualizer/dashboard.html', {'devise': devise})


@admin_required
@require_http_methods(['GET'])
def api_device_readings(request, device_id):
    """Paginated, searchable list of this device's SoiLENZ readings — for the
    'All Readings' sidebar search. Never returns the full reading history at
    once (a device can have tens of thousands of readings)."""
    devise = _get_soilenz_devise(device_id)
    qs     = DeviseApis.objects.filter(device=devise).order_by('-created_at')

    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        filters = Q(crop_type__icontains=q) | Q(area_name__icontains=q)
        if q.isdigit():
            filters |= Q(pk=int(q))
        qs = qs.filter(filters)

    page_size = min(50, max(1, int(request.GET.get('page_size', 20))))
    paginator = Paginator(qs, page_size)
    page      = paginator.get_page(request.GET.get('page', 1))

    linked_map = {}
    for reading_id, point_id in Point.objects.filter(reading__in=page.object_list).values_list('reading_id', 'id'):
        linked_map.setdefault(reading_id, []).append(point_id)

    results = [{
        'id': r.id,
        'latitude': r.latitude,
        'longitude': r.longitude,
        'crop_type': r.crop_type,
        'area_name': r.area_name,
        'created_at': r.created_at.isoformat(),
        'point_ids': linked_map.get(r.id, []),
        'parameters': {
            'ph': r.ph, 'ec': r.ec, 'n': r.nitrogen, 'p': r.phosphorous, 'k': r.potassium,
            'organic_carbon': r.oc, 's': r.sulphur, 'fe': r.iron, 'zn': r.zinc,
            'cu': r.copper, 'b': r.boron, 'mn': r.manganese,
        },
    } for r in page.object_list]

    return JsonResponse({
        'results': results,
        'page': page.number,
        'num_pages': paginator.num_pages,
        'count': paginator.count,
    })


@admin_required
@require_http_methods(['GET'])
def api_all_points(request, device_id):
    """Every point for this device, across all plots — 'Added to Map' shows
    one flat list since each add action creates its own small plot+point
    together (a plot is now just the boundary behind one entry, not
    something you pick before adding)."""
    devise = _get_soilenz_devise(device_id)
    points = Point.objects.filter(devise=devise).select_related('reading', 'plot')
    return JsonResponse([_point_json(p) for p in points], safe=False)


@admin_required
@require_http_methods(['GET', 'POST'])
def api_plots(request, device_id):
    devise = _get_soilenz_devise(device_id)

    if request.method == 'GET':
        plots = Plot.objects.filter(devise=devise)
        data = [{
            'id': p.id, 'name': p.name, 'geometry': p.geometry,
            'points_count': p.points.count(),
            'created_at': p.created_at.isoformat(),
        } for p in plots]
        return JsonResponse(data, safe=False)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    name     = (body.get('name') or '').strip()
    geometry = body.get('geometry')
    if not name:
        return JsonResponse({'error': 'name is required.'}, status=400)
    if not isinstance(geometry, dict) or geometry.get('type') != 'Polygon' or 'coordinates' not in geometry:
        return JsonResponse({'error': "geometry must be a GeoJSON Polygon."}, status=400)

    plot = Plot.objects.create(devise=devise, name=name, geometry=geometry)
    return JsonResponse({
        'id': plot.id, 'name': plot.name, 'geometry': plot.geometry,
        'points_count': 0, 'created_at': plot.created_at.isoformat(),
    }, status=201)


@admin_required
@require_http_methods(['DELETE'])
def api_plot_detail(request, device_id, plot_id):
    devise = _get_soilenz_devise(device_id)
    plot   = get_object_or_404(Plot, pk=plot_id, devise=devise)
    plot.delete()
    return JsonResponse({'success': True})


def _create_point_from_body(devise, plot, body):
    """Shared create logic for the plot-scoped points endpoint. The point's
    coordinates default to the plot's polygon centroid (via Point.save()) —
    a point is created by drawing a boundary, not by picking a lat/long."""
    reading_id = body.get('reading_id')
    lat = body.get('latitude')
    lon = body.get('longitude')

    if reading_id:
        reading = get_object_or_404(DeviseApis, pk=reading_id, device=devise)
        if lat is None:
            lat = reading.latitude or None
        if lon is None:
            lon = reading.longitude or None
        coordinates = {'lat': lat, 'lon': lon} if (lat and lon) else None
        point = Point.objects.create(
            devise=devise, plot=plot, reading=reading, coordinates=coordinates,
            sample_date=reading.created_at.date(),
            notes=body.get('notes') or None,
        )
        return JsonResponse(_point_json(point), status=201)

    # Manual point (not linked to any reading)
    from django.utils.dateparse import parse_date

    date_raw = body.get('sample_date')
    params   = body.get('parameters') or {}

    if not date_raw:
        return JsonResponse({'error': 'sample_date is required.'}, status=400)
    date = parse_date(date_raw)
    if not date:
        return JsonResponse({'error': 'sample_date must be in YYYY-MM-DD format.'}, status=400)
    if not params:
        return JsonResponse({'error': 'At least one soil parameter reading must be provided.'}, status=400)

    cleaned = {}
    for key, val in params.items():
        if key not in PARAMETER_DEFAULTS:
            return JsonResponse({'error': f"Invalid parameter key: '{key}'."}, status=400)
        try:
            num_val = float(val)
        except (TypeError, ValueError):
            return JsonResponse({'error': f"Value for '{key}' must be a number."}, status=400)
        limits = PARAMETER_DEFAULTS[key]
        if not (limits['min'] <= num_val <= limits['max']):
            return JsonResponse({'error': f"'{key}' value {num_val} must be between {limits['min']} and {limits['max']}."}, status=400)
        cleaned[key] = num_val

    coordinates = {'lat': lat, 'lon': lon} if (lat and lon) else None
    point = Point.objects.create(
        devise=devise, plot=plot, coordinates=coordinates, parameters=cleaned,
        sample_date=date, notes=body.get('notes') or None,
    )
    return JsonResponse(_point_json(point), status=201)


@admin_required
@require_http_methods(['GET', 'POST'])
def api_points(request, device_id, plot_id):
    devise = _get_soilenz_devise(device_id)
    plot   = get_object_or_404(Plot, pk=plot_id, devise=devise)

    if request.method == 'GET':
        points = plot.points.select_related('reading')
        return JsonResponse([_point_json(p) for p in points], safe=False)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    return _create_point_from_body(devise, plot, body)


@admin_required
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def api_point_detail(request, device_id, point_id):
    devise = _get_soilenz_devise(device_id)
    point  = get_object_or_404(Point, pk=point_id, devise=devise)

    if request.method == 'GET':
        return JsonResponse(_point_json(point))

    if request.method == 'DELETE':
        point.delete()
        return JsonResponse({'success': True})

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    if 'latitude' in body or 'longitude' in body:
        coords = dict(point.coordinates or {})
        if 'latitude' in body:
            coords['lat'] = body['latitude']
        if 'longitude' in body:
            coords['lon'] = body['longitude']
        point.coordinates = coords
    if 'notes' in body:
        point.notes = body['notes'] or None
    if 'sample_date' in body and not point.reading_id:
        from django.utils.dateparse import parse_date
        parsed = parse_date(body['sample_date']) if body['sample_date'] else None
        if not parsed:
            return JsonResponse({'error': 'sample_date must be in YYYY-MM-DD format.'}, status=400)
        point.sample_date = parsed
    if 'parameters' in body and not point.reading_id:
        params = body['parameters'] or {}
        cleaned = {}
        for key, val in params.items():
            if key not in PARAMETER_DEFAULTS:
                return JsonResponse({'error': f"Invalid parameter key: '{key}'."}, status=400)
            try:
                num_val = float(val)
            except (TypeError, ValueError):
                return JsonResponse({'error': f"Value for '{key}' must be a number."}, status=400)
            limits = PARAMETER_DEFAULTS[key]
            if not (limits['min'] <= num_val <= limits['max']):
                return JsonResponse({'error': f"'{key}' value {num_val} must be between {limits['min']} and {limits['max']}."}, status=400)
            cleaned[key] = num_val
        point.parameters = cleaned

    point.save()
    return JsonResponse(_point_json(point))


@admin_required
@require_http_methods(['GET'])
def api_raster(request, device_id, plot_id):
    devise = _get_soilenz_devise(device_id)
    plot   = get_object_or_404(Plot, pk=plot_id, devise=devise)

    parameter = request.GET.get('parameter', 'ph')
    if parameter not in PARAMETER_DEFAULTS:
        return JsonResponse({'error': f"Invalid parameter. Allowed: {list(PARAMETER_DEFAULTS.keys())}"}, status=400)

    points = list(plot.points.select_related('reading'))
    valid_points = [p for p in points if p.coordinates and parameter in p.get_parameters()]

    if not valid_points:
        return JsonResponse({
            'parameter': parameter, 'method': 'none',
            'min_value': None, 'max_value': None, 'resolution': [0, 0], 'cells': [],
        })

    from shapely.geometry import shape, Point as ShapelyPoint

    try:
        plot_geom = shape(plot.geometry)
    except Exception as exc:
        return JsonResponse({'error': f"Invalid plot geometry: {exc}"}, status=500)

    min_lng, min_lat, max_lng, max_lat = plot_geom.bounds

    try:
        grid_size = min(150, max(20, int(request.GET.get('resolution', '60'))))
    except ValueError:
        grid_size = 60

    lat_edges = np.linspace(min_lat, max_lat, grid_size + 1)
    lng_edges = np.linspace(min_lng, max_lng, grid_size + 1)
    lat_centers = (lat_edges[:-1] + lat_edges[1:]) / 2.0
    lng_centers = (lng_edges[:-1] + lng_edges[1:]) / 2.0

    grid_centroids = []
    grid_cells = []
    for i in range(grid_size):
        for j in range(grid_size):
            lat_c, lng_c = lat_centers[i], lng_centers[j]
            if plot_geom.contains(ShapelyPoint(lng_c, lat_c)):
                grid_cells.append({
                    'bounds': [[float(lat_edges[i]), float(lng_edges[j])], [float(lat_edges[i+1]), float(lng_edges[j+1])]],
                    'centroid': [float(lat_c), float(lng_c)],
                })
                grid_centroids.append([lat_c, lng_c])

    if not grid_centroids:
        return JsonResponse({
            'parameter': parameter, 'method': 'none',
            'min_value': None, 'max_value': None, 'resolution': [0, 0], 'cells': [],
        })

    grid_centroids_arr = np.array(grid_centroids)
    point_coords = np.array([[p.coordinates['lat'], p.coordinates['lon']] for p in valid_points])
    point_values = np.array([p.get_parameters()[parameter] for p in valid_points])

    if len(valid_points) == 1:
        dists_to_centroids = np.linalg.norm(grid_centroids_arr - point_coords[0], axis=1)
        max_dist = float(np.max(dists_to_centroids)) if len(dists_to_centroids) > 0 else 1.0
        interpolator = SingleSampleGradientInterpolator()
        interpolated_values = interpolator.interpolate(grid_centroids_arr, point_coords, point_values, parameter, max_dist=max_dist)
        method = 'single_sample_gradient'
    else:
        interpolator = IDWInterpolator()
        interpolated_values = interpolator.interpolate(grid_centroids_arr, point_coords, point_values, parameter)
        method = 'idw'

    min_val = float(np.min(interpolated_values))
    max_val = float(np.max(interpolated_values))
    for idx, val in enumerate(interpolated_values):
        grid_cells[idx]['value'] = float(val)

    return JsonResponse({
        'parameter': parameter, 'method': method,
        'min_value': min_val, 'max_value': max_val,
        'resolution': [grid_size, grid_size], 'cells': grid_cells,
    })
