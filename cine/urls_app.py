from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cartelera/", views.program_list, name="program_list"),
    path("proximos-estrenos/", views.upcoming, name="upcoming"),
    path("programas/<int:pk>/", views.program_detail, name="program_detail"),
    path("contacto/", views.contact, name="contact"),
    path("legales/<slug:slug>/", views.legal_page, name="legal_page"),
    path("registrarse/", views.register, name="register"),
    path("verificar-email/<str:token>/", views.verify_email, name="verify_email"),
    path("reenviar-verificacion/", views.resend_verification, name="resend_verification"),
    path("ingresar/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("salir/", views.logout_view, name="logout"),
    path("funciones/<int:pk>/reservar/", views.reserve, name="reserve"),
    path("mis-reservas/", views.my_reservations, name="my_reservations"),
    path("reservas/<str:code>/", views.reservation_detail, name="reservation_detail"),
    path("boleteria/", views.checkin, name="checkin"),
]
