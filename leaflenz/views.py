from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponseForbidden

from agriapp.models import Devise, DeviseApisFields


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


class LeafLenzDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'leaflenz/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        devices = Devise.objects.filter(devise_type='leaflenz')

        for device in devices:
            device.scan_count = DeviseApisFields.objects.filter(device=device).count()

        context['devices']     = devices
        context['active_page'] = 'leaflenz'
        return context


@login_required
@ensure_csrf_cookie
def leaflenz_scan_view(request, device_id):
    """User-facing scan page — only their own device."""
    device = get_object_or_404(Devise, pk=device_id, user=request.user)
    return render(request, 'leaflenz/scan.html', {'device': device})


@ensure_csrf_cookie
def leaflenz_admin_scan_view(request, device_id):
    """Admin-facing scan page — any device, staff/superuser only."""
    if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
        return HttpResponseForbidden()
    device = get_object_or_404(Devise, pk=device_id, devise_type='leaflenz')
    return render(request, 'leaflenz/scan_admin.html', {'device': device})
