from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponseForbidden

from agriapp.models import Devise, DeviseApisFields
from agri_ai.fruit import FRUIT_INFO, SUPPORTED_FRUITS


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


def _fruit_choices():
    return [(key, FRUIT_INFO[key]['name']) for key in SUPPORTED_FRUITS]


class HarvestLenzDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'harvestlenz/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        devices = Devise.objects.filter(devise_type='harvestlenz')

        for device in devices:
            device.scan_count = DeviseApisFields.objects.filter(device=device).count()

        context['devices']     = devices
        context['active_page'] = 'harvestlenz'
        return context


@login_required
@ensure_csrf_cookie
def harvestlenz_scan_view(request, device_id):
    """User-facing scan page — only their own device."""
    device = get_object_or_404(Devise, pk=device_id, user=request.user, devise_type='harvestlenz')
    return render(request, 'harvestlenz/scan.html', {'device': device, 'fruit_choices': _fruit_choices()})


@ensure_csrf_cookie
def harvestlenz_admin_scan_view(request, device_id):
    """Admin-facing scan page — any device, staff/superuser only."""
    if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
        return HttpResponseForbidden()
    device = get_object_or_404(Devise, pk=device_id, devise_type='harvestlenz')
    return render(request, 'harvestlenz/scan_admin.html', {'device': device, 'fruit_choices': _fruit_choices()})
