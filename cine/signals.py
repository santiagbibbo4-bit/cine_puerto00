from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import LegalPage, SiteSetting


@receiver(post_migrate)
def create_site_defaults(sender, **kwargs):
    if sender.name != "cine":
        return
    LegalPage.objects.get_or_create(
        slug="privacidad",
        defaults={
            "title": "Política de privacidad",
            "body": (
                "BORRADOR PENDIENTE DE REVISIÓN LEGAL\n\n"
                "Qué datos recolectamos\nPara crear una cuenta y reservar entradas solicitamos email y contraseña. "
                "No pedimos ni almacenamos datos de tarjetas.\n\n"
                "Uso de los datos\nEl email se utiliza para verificar la cuenta, enviar comprobantes de reserva y "
                "comunicar cambios de funciones.\n\n"
                "Derechos\nCompletar cómo acceder, rectificar o eliminar datos y los datos de contacto del responsable."
            ),
        },
    )
    LegalPage.objects.get_or_create(
        slug="condiciones",
        defaults={
            "title": "Términos y condiciones",
            "body": (
                "BORRADOR PENDIENTE DE REVISIÓN LEGAL\n\n"
                "Reservas\nLas reservas son por cantidad de entradas; no se eligen butacas y los asientos se asignan "
                "al llegar. Cada reserva tiene un código grupal que se valida una sola vez en boletería.\n\n"
                "Pagos\nEsta versión no incluye pagos online. Completar cómo y cuándo se abonan las entradas.\n\n"
                "Cancelaciones y llegada tarde\nCompletar la política de cancelación, tolerancia de llegada y "
                "reasignación de lugares."
            ),
        },
    )
    for key, value in {
        "cinema_name": "Cine de Cortos",
        "cinema_address": "[Completar: dirección del cine]",
        "cinema_email": "[Completar: email de contacto]",
        "cinema_phone": "[Completar: teléfono]",
        "cinema_hours": "[Completar: horarios de atención]",
    }.items():
        SiteSetting.objects.get_or_create(key=key, defaults={"value": value})
