import base64
import hashlib
import io
import logging
import re
import secrets
import smtplib
import string
from datetime import timedelta

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import BadHeaderError, EmailMessage
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    CheckInForm,
    ProgramManagementForm,
    RegistrationForm,
    ReservationForm,
    ScreeningManagementFormSet,
    ShortFilmManagementFormSet,
)
from .models import EmailVerification, LegalPage, Program, Reservation, Screening

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    pass


def _deliver_email(subject, body, recipients, attachments=()):
    try:
        message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
        for filename, content, content_type in attachments:
            message.attach(filename, content, content_type)
        message.send(fail_silently=False)
    except (BadHeaderError, OSError, smtplib.SMTPException) as error:
        smtp_code = getattr(error, "smtp_code", None)
        logger.error(
            "Falló el envío de email (%s; código SMTP: %s).",
            type(error).__name__,
            smtp_code if smtp_code is not None else "sin respuesta",
        )
        raise EmailDeliveryError from error


def _qr_png(code):
    output = io.BytesIO()
    qrcode.make(code).save(output, format="PNG")
    return output.getvalue()


def _published_programs():
    return Program.objects.filter(status=Program.Status.PUBLISHED)


def _upcoming_screenings(program_id=None):
    qs = Screening.objects.select_related("program").filter(
        status__in=[Screening.Status.PUBLISHED, Screening.Status.CANCELLED],
        starts_at__gt=timezone.now(),
        program__status=Program.Status.PUBLISHED,
    )
    return qs.filter(program_id=program_id) if program_id else qs


def _new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))


def _normalize_code(value):
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def _send_verification(user):
    EmailVerification.objects.filter(user=user, used_at__isnull=True).delete()
    token = secrets.token_urlsafe(32)
    EmailVerification.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(hours=24),
    )
    link = f"{settings.SITE_URL}{reverse('verify_email', args=[token])}"
    _deliver_email(
        f"Verificá tu email · {settings.DEFAULT_FROM_EMAIL.split('<')[0].strip()}",
        f"Confirmá tu email para reservar entradas: {link}\nEl enlace vence en 24 horas.",
        [user.email],
    )


def _send_reservation_confirmation(reservation):
    screening = reservation.screening
    link = f"{settings.SITE_URL}{reverse('reservation_detail', args=[reservation.code])}"
    _deliver_email(
        "Tu reserva está confirmada",
        (
            f"Reserva {reservation.code}\nPrograma: {screening.program.title}\n"
            f"Función: {timezone.localtime(screening.starts_at):%d/%m/%Y %H:%M} · Sala {screening.room}\n"
            f"Cantidad: {reservation.quantity}\nComprobante: {link}\n"
            "Presentá el código o el QR adjunto en boletería. No se realizó ningún pago online."
        ),
        [reservation.user.email],
        [(f"reserva-{reservation.code}.png", _qr_png(reservation.code), "image/png")],
    )


def home(request):
    programs = list(_published_programs().filter(featured=True).annotate(short_count=Count("shorts"))[:6])
    if not programs:
        programs = list(_published_programs().annotate(short_count=Count("shorts"))[:5])
    for program in programs:
        program.next_screening = _upcoming_screenings(program.pk).filter(status=Screening.Status.PUBLISHED).order_by("starts_at").first()
        program.trailer_safe = bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", program.trailer_youtube_id or ""))
    soon = _upcoming_screenings().filter(status=Screening.Status.PUBLISHED).order_by("starts_at")[:8]
    return render(request, "cine/home.html", {"featured": programs, "soon": soon})


def program_list(request):
    sala = request.GET.get("sala", "")
    dia = request.GET.get("dia", "")
    if sala not in dict(Screening.Room.choices):
        sala = ""
    try:
        filter_day = timezone.datetime.strptime(dia, "%Y-%m-%d").date() if dia else None
    except ValueError:
        filter_day = None
        dia = ""
    programs = _published_programs().annotate(short_count=Count("shorts"))
    entries = []
    for program in programs:
        screenings = _upcoming_screenings(program.pk)
        if sala:
            screenings = screenings.filter(room=sala)
        if filter_day:
            screenings = screenings.filter(starts_at__date=filter_day)
        screenings = list(screenings.order_by("starts_at"))
        if screenings:
            entries.append({"program": program, "screenings": screenings})
    days = _upcoming_screenings().filter(status=Screening.Status.PUBLISHED).dates("starts_at", "day")[:14]
    return render(request, "cine/program_list.html", {"entries": entries, "sala": sala, "dia": dia, "days": days})


def upcoming(request):
    programs = _published_programs().filter(release_date__gt=timezone.localdate()).order_by("release_date")
    return render(request, "cine/upcoming.html", {"programs": programs})


def program_detail(request, pk):
    program = get_object_or_404(_published_programs().annotate(short_count=Count("shorts")), pk=pk)
    program.trailer_safe = bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", program.trailer_youtube_id or ""))
    screenings = _upcoming_screenings(program.pk).order_by("starts_at")
    return render(
        request,
        "cine/program_detail.html",
        {"program": program, "screenings": screenings, "shorts": program.shorts.all()},
    )


def contact(request):
    return render(request, "cine/contact.html")


def _is_staff(user):
    return user.is_authenticated and user.is_staff


@user_passes_test(_is_staff)
def management_dashboard(request):
    programs = Program.objects.annotate(short_count=Count("shorts")).prefetch_related("screenings").order_by(
        "-created_at"
    )
    return render(request, "cine/management_dashboard.html", {"programs": programs})


@user_passes_test(_is_staff)
@require_http_methods(["GET", "POST"])
def manage_program(request, pk=None):
    program = get_object_or_404(Program, pk=pk) if pk is not None else Program()
    creating = pk is None

    if request.method == "POST":
        form = ProgramManagementForm(request.POST, request.FILES, instance=program)
        screenings = ScreeningManagementFormSet(request.POST, instance=program, prefix="screenings")
        shorts = ShortFilmManagementFormSet(request.POST, instance=program, prefix="shorts")
        if form.is_valid() and screenings.is_valid() and shorts.is_valid():
            with transaction.atomic():
                saved_program = form.save()
                screenings.instance = saved_program
                shorts.instance = saved_program
                screenings.save()
                shorts.save()
            messages.success(request, f"Se guardaron los cambios de “{saved_program.title}”.")
            return redirect("management_dashboard")
    else:
        form = ProgramManagementForm(instance=program)
        screenings = ScreeningManagementFormSet(instance=program, prefix="screenings")
        shorts = ShortFilmManagementFormSet(instance=program, prefix="shorts")

    return render(
        request,
        "cine/management_program_form.html",
        {
            "program": program,
            "creating": creating,
            "form": form,
            "screenings": screenings,
            "shorts": shorts,
        },
    )


@user_passes_test(_is_staff)
@require_POST
def delete_program(request, pk):
    program = get_object_or_404(Program, pk=pk)
    if Reservation.objects.filter(screening__program=program).exists():
        messages.error(request, "No se puede eliminar: el programa tiene reservas. Despublicalo o cancelá sus funciones.")
    else:
        program.delete()
        messages.success(request, "Programa eliminado.")
    return redirect("management_dashboard")


def legal_page(request, slug):
    page = get_object_or_404(LegalPage, slug=slug)
    return render(request, "cine/legal.html", {"page": page})


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            _send_verification(user)
            messages.success(request, "Cuenta creada. Revisá tu email para verificarla antes de reservar.")
        except EmailDeliveryError:
            messages.warning(request, "La cuenta se creó, pero no pudimos enviar el email. Ingresá y pedí que te lo reenviemos.")
        return redirect("login")
    return render(request, "registration/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def verify_email(request, token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    verification = EmailVerification.objects.filter(
        token_hash=token_hash, used_at__isnull=True, expires_at__gt=timezone.now()
    ).select_related("user").first()
    if request.method == "GET":
        return render(request, "cine/verify_email.html", {"valid": verification is not None, "token": token})
    if not verification:
        messages.error(request, "El enlace de verificación no es válido o venció.")
        return redirect("login")
    with transaction.atomic():
        changed = EmailVerification.objects.filter(pk=verification.pk, used_at__isnull=True, expires_at__gt=timezone.now()).update(used_at=timezone.now())
        if changed:
            type(verification.user).objects.filter(pk=verification.user_id).update(email_verified=True)
    if changed:
        messages.success(request, "Email verificado. Ya podés reservar entradas.")
    else:
        messages.error(request, "El enlace ya fue utilizado.")
    return redirect("login")


@login_required
@require_POST
def resend_verification(request):
    if request.user.email_verified:
        messages.info(request, "Tu email ya está verificado.")
        return redirect("home")
    try:
        _send_verification(request.user)
        messages.success(request, "Te enviamos un nuevo enlace de verificación.")
    except EmailDeliveryError:
        messages.error(request, "No pudimos enviar el email ahora. Probá de nuevo más tarde.")
    return redirect("home")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


def _create_reservation(user, screening_id, quantity, key):
    try:
        with transaction.atomic():
            duplicate = Reservation.objects.filter(user=user, idempotency_key=key).first() if key else None
            if duplicate:
                return duplicate, True
            screening = Screening.objects.select_related("program").filter(
                pk=screening_id, status=Screening.Status.PUBLISHED, program__status=Program.Status.PUBLISHED
            ).first()
            if not screening:
                raise ValueError("La función no está disponible.")
            if screening.starts_at <= timezone.now() + timedelta(minutes=settings.BOOKING_CUTOFF_MINUTES):
                raise ValueError("Las reservas para esta función ya cerraron.")
            if quantity < 1 or quantity > settings.MAX_TICKETS_PER_BOOKING:
                raise ValueError(f"Podés reservar entre 1 y {settings.MAX_TICKETS_PER_BOOKING} entradas.")
            reserved = Screening.objects.filter(
                pk=screening.pk, status=Screening.Status.PUBLISHED, booked_count__lte=F("capacity") - quantity
            ).update(booked_count=F("booked_count") + quantity)
            if not reserved:
                screening.refresh_from_db()
                if screening.remaining <= 0:
                    raise ValueError("La función está agotada.")
                raise ValueError(f"Solo quedan {screening.remaining} lugares disponibles.")
            reservation = Reservation.objects.create(
                user=user, screening=screening, quantity=quantity, code=_new_code(), idempotency_key=key or None
            )
            return reservation, False
    except IntegrityError:
        if key:
            duplicate = Reservation.objects.filter(user=user, idempotency_key=key).first()
            if duplicate:
                return duplicate, True
        raise


@login_required
@require_http_methods(["GET", "POST"])
def reserve(request, pk):
    screening = get_object_or_404(Screening.objects.select_related("program"), pk=pk)
    if screening.status == Screening.Status.DRAFT or screening.program.status != Program.Status.PUBLISHED:
        raise Http404
    if request.method == "POST":
        form = ReservationForm(request.POST)
        if not request.user.email_verified:
            messages.error(request, "Verificá tu email antes de reservar.")
        elif form.is_valid():
            try:
                reservation, duplicate = _create_reservation(request.user, screening.pk, form.cleaned_data["quantity"], form.cleaned_data["key"])
                if not duplicate:
                    try:
                        _send_reservation_confirmation(reservation)
                        reservation.email_sent_at = timezone.now()
                        reservation.save(update_fields=["email_sent_at"])
                        messages.success(request, "Reserva confirmada. Te enviamos el comprobante.")
                    except EmailDeliveryError:
                        messages.warning(request, "Tu reserva está confirmada, pero no pudimos enviar el email. Guardá tu código.")
                return redirect("reservation_detail", code=reservation.code)
            except ValueError as error:
                form.add_error(None, str(error))
        messages.error(request, "Revisá los datos de la reserva.")
    else:
        form = ReservationForm(initial={"quantity": 1, "key": secrets.token_urlsafe(12)})
    return render(request, "cine/reserve.html", {
        "screening": screening,
        "form": form,
        "quantity_options": range(1, max(1, min(settings.MAX_TICKETS_PER_BOOKING, screening.remaining)) + 1),
        "max_tickets": settings.MAX_TICKETS_PER_BOOKING,
    })


@login_required
def my_reservations(request):
    rows = Reservation.objects.select_related("screening__program").filter(user=request.user)
    return render(request, "cine/my_reservations.html", {"reservations": rows})


@login_required
def reservation_detail(request, code):
    reservation = get_object_or_404(
        Reservation.objects.select_related("screening__program", "user"), code=_normalize_code(code), user=request.user
    )
    qr_data = base64.b64encode(_qr_png(reservation.code)).decode("ascii")
    return render(request, "cine/reservation_detail.html", {"reservation": reservation, "qr_data": qr_data})


@user_passes_test(_is_staff)
@require_http_methods(["GET", "POST"])
def checkin(request):
    form = CheckInForm(request.POST or None)
    result = None
    reservation = None
    if request.method == "POST" and form.is_valid():
        code = _normalize_code(form.cleaned_data["code"])
        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().select_related("screening__program", "user").filter(code=code).first()
            if not reservation:
                result = "not_found"
            elif reservation.status == Reservation.Status.CANCELLED:
                result = "cancelled"
            elif reservation.status == Reservation.Status.CHECKED_IN:
                result = "already_used"
            else:
                updated = Reservation.objects.filter(pk=reservation.pk, status=Reservation.Status.CONFIRMED).update(
                    status=Reservation.Status.CHECKED_IN, checked_in_at=timezone.now(), checked_in_by=request.user
                )
                result = "ok" if updated else "already_used"
                reservation.refresh_from_db()
    return render(request, "cine/checkin.html", {"form": form, "result": result, "reservation": reservation})
