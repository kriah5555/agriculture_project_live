from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.http import FileResponse, Http404
from .models import AppVersion
import urllib.parse
import mimetypes
import os

CONTENT_TYPE_MAP = {
    '.zip'   : 'application/zip',
    '.apk'   : 'application/vnd.android.package-archive',
    '.rar'   : 'application/vnd.rar',
    '.tar.gz': 'application/gzip',
}

# API 1: Check if given version is active

@api_view(['GET'])
@permission_classes([AllowAny])
def check_active_version(request):
    """
    URL: /api/check-active-version/?version=v1.0.0
    Response:
    - If sent version is same as active version: { "version": "v1.0.0", "update": 0, "message": "You have the latest version" }
    - If sent version is different from active version: { "version": "v1.0.0", "update": 1, "message": "Update available: v1.2.0" }
    - If no active version: { "version": "v1.0.0", "update": 1, "message": "No active version available, please update" }
    """

    # Get version from query params
    version_str = request.query_params.get('version')

    if not version_str:
        return Response({
            "version": None,
            "update": 1,
            "message": "Version parameter is missing"
        })

    # Get the active version from DB
    active_version = AppVersion.objects.filter(is_active=True).first()

    if not active_version:
        return Response({
            "version": version_str,
            "update": 1,
            "message": "No active version available, please update"
        })

    # Compare sent version with active
    if version_str == active_version.version:
        return Response({
            "version": version_str,
            "update": 0,
            "message": "You have the latest version"
        })
    else:
        return Response({
            "version": version_str,
            "update": 1,
            "message": f"Update available: {active_version.version}"
        })


# API 2: Download zip file for a given version
@api_view(['GET'])
@permission_classes([AllowAny])
def download_active_version(request):
    """
    URL: /versions/api/download-version/

    Response:
      - Sends the file of the currently active version (with its original extension)
      - Sends JSON if no active version exists
    """
    # Get the currently active version
    version_obj = AppVersion.objects.filter(is_active=True).first()

    if not version_obj or not version_obj.zip_file:
        return Response({
            "version": None,
            "active": 0,
            "message": "No active version available"
        })

    # Get the original file extension
    original_filename = os.path.basename(version_obj.zip_file.name)
    _, ext = os.path.splitext(original_filename)
    version_filename        = f"{version_obj.version}{ext}"
    version_filename_quoted = urllib.parse.quote(version_filename)
    content_type            = CONTENT_TYPE_MAP.get(ext.lower(), 'application/octet-stream')

    try:
        response = FileResponse(version_obj.zip_file.open('rb'), content_type=content_type)
        response['Content-Disposition'] = (
            f'attachment; filename="{version_filename}"; '
            f"filename*=UTF-8''{version_filename_quoted}"
        )
        return response
    except FileNotFoundError:
        raise Http404("File not found on server")
