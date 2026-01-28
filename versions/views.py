from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import AppVersion
from .forms import AppVersionForm

def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def version_list(request):
    versions = AppVersion.objects.all().order_by('-created_at')
    return render(request, 'versions/version_list.html', {
        'versions': versions
    })

@login_required
@user_passes_test(is_admin)
def version_create(request):
    if request.method == 'POST':
        form = AppVersionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('version_list')
    else:
        form = AppVersionForm()

    return render(request, 'versions/version_form.html', {
        'form': form,
        'title': 'Add Version'
    })

@login_required
@user_passes_test(is_admin)
def version_update(request, pk):
    version = get_object_or_404(AppVersion, pk=pk)

    if request.method == 'POST':
        form = AppVersionForm(request.POST, request.FILES, instance=version)
        if form.is_valid():
            form.save()
            return redirect('version_list')
    else:
        form = AppVersionForm(instance=version)

    return render(request, 'versions/version_form.html', {
        'form': form,
        'title': 'Edit Version'
    })

@login_required
@user_passes_test(is_admin)
def version_delete(request, pk):
    version = get_object_or_404(AppVersion, pk=pk)

    if request.method == 'POST':
        version.delete()
        return redirect('version_list')

    return render(request, 'versions/version_confirm_delete.html', {
        'version': version
    })
