from django.conf import settings
from django.utils import timezone

from .models import SiteSetting


def cinema_settings(request):
    values = {item.key: item.value for item in SiteSetting.objects.all()}
    return {
        "cinema_name": values.get("cinema_name", "Cine de Cortos"),
        "cinema_address": values.get("cinema_address", "[Completar: dirección del cine]"),
        "cinema_email": values.get("cinema_email", "[Completar: email de contacto]"),
        "cinema_phone": values.get("cinema_phone", "[Completar: teléfono]"),
        "cinema_hours": values.get("cinema_hours", "[Completar: horarios de atención]"),
        "booking_cutoff_minutes": settings.BOOKING_CUTOFF_MINUTES,
        "today": timezone.localdate(),
    }
