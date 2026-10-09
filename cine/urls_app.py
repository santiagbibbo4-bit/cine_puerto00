from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

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
    path(
        "recuperar-clave/",
        auth_views.PasswordResetView.as_view(
            template_name="cine/password_reset_form.html",
            email_template_name="cine/password_reset_email.txt",
            subject_template_name="cine/password_reset_subject.txt",
            success_url=reverse_lazy("cine_password_reset_done"),
        ),
        name="cine_password_reset",
    ),
    path(
        "recuperar-clave/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="cine/password_reset_done.html",
        ),
        name="cine_password_reset_done",
    ),
    path(
        "recuperar-clave/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="cine/password_reset_confirm.html",
            success_url=reverse_lazy("cine_password_reset_complete"),
        ),
        name="cine_password_reset_confirm",
    ),
    path(
        "recuperar-clave/completa/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="cine/password_reset_complete.html",
        ),
        name="cine_password_reset_complete",
    ),
    path(
        "cambiar-clave/",
        auth_views.PasswordChangeView.as_view(
            template_name="cine/password_change_form.html",
            success_url=reverse_lazy("cine_password_change_done"),
        ),
        name="cine_password_change",
    ),
    path(
        "cambiar-clave/completa/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="cine/password_change_done.html",
        ),
        name="cine_password_change_done",
    ),
    path("salir/", views.logout_view, name="logout"),
    path("funciones/<int:pk>/reservar/", views.reserve, name="reserve"),
    path("mis-reservas/", views.my_reservations, name="my_reservations"),
    path("reservas/<str:code>/", views.reservation_detail, name="reservation_detail"),
    path("boleteria/", views.checkin, name="checkin"),
]
