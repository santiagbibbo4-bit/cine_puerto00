from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path("admin/", views.management_dashboard, name="management_dashboard"),
    path("admin/programas/nuevo/", views.manage_program, name="manage_program_create"),
    path("admin/programas/<int:pk>/", views.manage_program, name="manage_program_edit"),
    path("admin/programas/<int:pk>/eliminar/", views.delete_program, name="manage_program_delete"),
    path("admin/django/", admin.site.urls),
    path("", include("cine.urls_app")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
