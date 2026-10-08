import hashlib
import re
import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ScreeningManagementFormSet
from .models import EmailVerification, Program, Reservation, Screening
from .views import EmailDeliveryError, _deliver_email

User = get_user_model()


class EmailDeliveryTests(TestCase):
    @patch("cine.views.EmailMessage.send", side_effect=smtplib.SMTPServerDisconnected("server closed"))
    def test_smtp_failure_is_reported_as_email_delivery_error(self, _send):
        with self.assertLogs("cine.views", level="ERROR") as logs:
            with self.assertRaises(EmailDeliveryError):
                _deliver_email("Prueba", "Texto", ["cine@example.com"])
        self.assertIn("SMTPServerDisconnected", logs.output[0])


def make_screening(*, capacity=4, starts_in=timedelta(days=1), status=Screening.Status.PUBLISHED):
    program = Program.objects.create(title="Luz breve", synopsis="Una historia.", status=Program.Status.PUBLISHED)
    return Screening.objects.create(
        program=program,
        starts_at=timezone.now() + starts_in,
        room=Screening.Room.TWO_D,
        capacity=capacity,
        status=status,
    )


class PublicPagesTests(TestCase):
    def test_home_cartelera_detail_and_filter(self):
        screening = make_screening()
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertContains(self.client.get(reverse("program_list")), "Luz breve")
        detail = self.client.get(reverse("program_detail", args=[screening.program_id]))
        self.assertContains(detail, "Luz breve")
        filtered = self.client.get(reverse("program_list"), {"sala": "4D"})
        self.assertNotContains(filtered, "Luz breve")

    def test_draft_program_is_not_public(self):
        program = Program.objects.create(title="Oculto")
        response = self.client.get(reverse("program_detail", args=[program.pk]))
        self.assertEqual(response.status_code, 404)

    def test_full_screening_is_visible_as_sold_out(self):
        screening = make_screening(capacity=2)
        screening.booked_count = 2
        screening.save(update_fields=["booked_count"])
        response = self.client.get(reverse("program_list"))
        self.assertContains(response, "Completa · sin lugares")
        self.assertContains(response, "is-sold-out")

    def test_future_premiere_with_scheduled_screening_is_shown_in_upcoming_and_cartelera(self):
        program = Program.objects.create(
            title="Estreno futuro",
            release_date=timezone.localdate() + timedelta(days=10),
            status=Program.Status.PUBLISHED,
        )
        Screening.objects.create(
            program=program,
            starts_at=timezone.now() + timedelta(days=12),
            room=Screening.Room.TWO_D,
            capacity=40,
        )
        self.assertContains(self.client.get(reverse("upcoming")), program.title)
        self.assertContains(self.client.get(reverse("program_list")), program.title)


class SimpleManagementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="admin@example.com", password="A-secure-password-123", is_staff=True)
        self.client.force_login(self.staff)

    def test_simple_panel_loads_and_adds_program_with_screening_capacity(self):
        response = self.client.get(reverse("management_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agregar película o programa")

        local_start = timezone.localtime(timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        payload = {
            "title": "Cortos del barrio",
            "synopsis": "Una selección de historias breves.",
            "duration_min": "",
            "age_rating": "ATP",
            "trailer_youtube_id": "",
            "poster": "",
            "release_date": "",
            "featured": "on",
            "status": Program.Status.PUBLISHED,
            "screenings-TOTAL_FORMS": "3",
            "screenings-INITIAL_FORMS": "0",
            "screenings-MIN_NUM_FORMS": "0",
            "screenings-MAX_NUM_FORMS": "30",
            "screenings-0-starts_at": local_start,
            "screenings-0-room": Screening.Room.FOUR_D,
            "screenings-0-capacity": "42",
            "screenings-0-status": Screening.Status.PUBLISHED,
            "screenings-1-starts_at": "",
            "screenings-1-room": "",
            "screenings-1-capacity": "",
            "screenings-1-status": Screening.Status.PUBLISHED,
            "screenings-2-starts_at": local_start,
            "screenings-2-room": Screening.Room.TWO_D,
            "screenings-2-capacity": "30",
            "screenings-2-status": Screening.Status.PUBLISHED,
            "shorts-TOTAL_FORMS": "2",
            "shorts-INITIAL_FORMS": "0",
            "shorts-MIN_NUM_FORMS": "0",
            "shorts-MAX_NUM_FORMS": "30",
            "shorts-0-title": "La esquina",
            "shorts-0-director": "Ana",
            "shorts-0-duration_min": "8",
            "shorts-0-synopsis": "",
            "shorts-0-sort": "0",
            "shorts-1-title": "",
            "shorts-1-director": "",
            "shorts-1-duration_min": "",
            "shorts-1-synopsis": "",
            "shorts-1-sort": "0",
        }
        response = self.client.post(reverse("manage_program_create"), payload)
        self.assertRedirects(response, reverse("management_dashboard"))
        program = Program.objects.get(title="Cortos del barrio")
        self.assertTrue(program.featured)
        self.assertEqual(program.status, Program.Status.PUBLISHED)
        self.assertEqual(program.screenings.count(), 2)
        screening = program.screenings.get(room=Screening.Room.FOUR_D)
        self.assertEqual(screening.capacity, 42)
        self.assertEqual(program.shorts.get().title, "La esquina")
        self.assertContains(self.client.get(reverse("program_list")), "Cortos del barrio")

    def test_management_screening_formset_accepts_many_functions_and_rejects_same_room_time(self):
        program = Program.objects.create(title="Programa", status=Program.Status.PUBLISHED)
        starts_at = timezone.localtime(timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        payload = {
            "screenings-TOTAL_FORMS": "3",
            "screenings-INITIAL_FORMS": "0",
            "screenings-MIN_NUM_FORMS": "0",
            "screenings-MAX_NUM_FORMS": "1000",
        }
        for index, minute_offset in enumerate((0, 30, 60)):
            when = timezone.localtime(timezone.now() + timedelta(days=5, minutes=minute_offset)).strftime("%Y-%m-%dT%H:%M")
            payload.update({
                f"screenings-{index}-starts_at": when,
                f"screenings-{index}-room": Screening.Room.TWO_D,
                f"screenings-{index}-capacity": "30",
                f"screenings-{index}-status": Screening.Status.PUBLISHED,
            })
        formset = ScreeningManagementFormSet(payload, instance=program, prefix="screenings")
        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertEqual(len(formset.forms), 3)

        payload["screenings-2-starts_at"] = starts_at
        payload["screenings-0-starts_at"] = starts_at
        invalid_formset = ScreeningManagementFormSet(payload, instance=program, prefix="screenings")
        self.assertFalse(invalid_formset.is_valid())
        self.assertTrue(any("Ya existe otra función" in str(error) for error in invalid_formset.errors))

        existing_time = timezone.now() + timedelta(days=8)
        Screening.objects.create(
            program=program,
            starts_at=existing_time,
            room=Screening.Room.FOUR_D,
            capacity=20,
        )
        other_program = Program.objects.create(title="Otro programa")
        conflict_data = {
            "screenings-TOTAL_FORMS": "1",
            "screenings-INITIAL_FORMS": "0",
            "screenings-MIN_NUM_FORMS": "0",
            "screenings-MAX_NUM_FORMS": "1000",
            "screenings-0-starts_at": timezone.localtime(existing_time).strftime("%Y-%m-%dT%H:%M"),
            "screenings-0-room": Screening.Room.FOUR_D,
            "screenings-0-capacity": "20",
            "screenings-0-status": Screening.Status.PUBLISHED,
        }
        conflicting_formset = ScreeningManagementFormSet(conflict_data, instance=other_program, prefix="screenings")
        self.assertFalse(conflicting_formset.is_valid())
        self.assertIn("Ya existe otra función", str(conflicting_formset.errors))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver")
class AccountAndBookingTests(TestCase):
    def setUp(self):
        self.screening = make_screening(capacity=3)
        self.user = User.objects.create_user(email="cine@example.com", password="A-secure-passphrase-2026", email_verified=True)

    def test_registration_sends_single_use_email_verification_link(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "  nueva@example.com ",
                "password1": "Una-clave-segura-2026",
                "password2": "Una-clave-segura-2026",
                "accept_terms": "on",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(email="nueva@example.com")
        self.assertFalse(user.email_verified)
        token = re.search(r"/verificar-email/([^/\s]+)", mail.outbox[0].body).group(1)
        self.assertEqual(self.client.get(reverse("verify_email", args=[token])).status_code, 200)
        self.assertRedirects(self.client.post(reverse("verify_email", args=[token])), reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertRedirects(self.client.post(reverse("verify_email", args=[token])), reverse("login"))

    def test_unverified_user_cannot_reserve(self):
        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("reserve", args=[self.screening.pk]), {"quantity": 1, "key": "request-key-1234"}
        )
        self.assertEqual(Reservation.objects.count(), 0)
        self.screening.refresh_from_db()
        self.assertEqual(self.screening.booked_count, 0)
        self.assertEqual(response.status_code, 200)

    def test_booking_is_confirmed_and_duplicate_request_is_idempotent(self):
        self.client.force_login(self.user)
        payload = {"quantity": 2, "key": "booking-key-12345"}
        response = self.client.post(reverse("reserve", args=[self.screening.pk]), payload)
        reservation = Reservation.objects.get()
        self.assertRedirects(response, reverse("reservation_detail", args=[reservation.code]))
        self.assertEqual(reservation.quantity, 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].attachments[0][0], f"reserva-{reservation.code}.png")
        self.assertEqual(mail.outbox[0].attachments[0][2], "image/png")
        self.client.post(reverse("reserve", args=[self.screening.pk]), payload)
        self.assertEqual(Reservation.objects.count(), 1)
        self.screening.refresh_from_db()
        self.assertEqual(self.screening.booked_count, 2)
        self.assertContains(self.client.get(reverse("reservation_detail", args=[reservation.code])), "data:image/png;base64")

    def test_capacity_guard_prevents_overselling(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("reserve", args=[self.screening.pk]), {"quantity": 4, "key": "too-many-key-1234"}
        )
        self.assertEqual(Reservation.objects.count(), 0)
        self.screening.refresh_from_db()
        self.assertEqual(self.screening.booked_count, 0)
        self.assertContains(response, "Solo quedan 3 lugares")

    def test_per_booking_limit_is_enforced(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("reserve", args=[self.screening.pk]), {"quantity": 9, "key": "quantity-key-1234"}
        )
        self.assertContains(response, "entre 1 y 8 entradas")
        self.assertEqual(Reservation.objects.count(), 0)
        self.screening.refresh_from_db()
        self.assertEqual(self.screening.booked_count, 0)

    def test_cutoff_and_cancelled_screening_cannot_be_booked(self):
        self.client.force_login(self.user)
        soon = make_screening(starts_in=timedelta(minutes=10))
        closed = self.client.post(reverse("reserve", args=[soon.pk]), {"quantity": 1, "key": "closed-key-12345"})
        self.assertContains(closed, "ya cerraron")
        cancelled = make_screening(status=Screening.Status.CANCELLED)
        response = self.client.post(
            reverse("reserve", args=[cancelled.pk]), {"quantity": 1, "key": "cancel-key-12345"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_checkin_requires_staff_and_can_only_be_used_once(self):
        reservation = Reservation.objects.create(
            code="ABCDEFG234", user=self.user, screening=self.screening, quantity=2
        )
        self.screening.booked_count = 2
        self.screening.save(update_fields=["booked_count"])
        self.assertRedirects(
            self.client.get(reverse("checkin")),
            f"{reverse('login')}?next={reverse('checkin')}",
        )
        staff = User.objects.create_user(email="staff@example.com", password="Another-secure-pass-2026", is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse("checkin"), {"code": "abcde-1234"})
        self.assertContains(response, "No encontramos")
        response = self.client.post(reverse("checkin"), {"code": reservation.code})
        self.assertContains(response, "Ingreso autorizado")
        response = self.client.post(reverse("checkin"), {"code": reservation.code})
        self.assertContains(response, "ya fue utilizado")
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CHECKED_IN)

    def test_staff_checkin_route_does_not_disclose_to_anonymous(self):
        response = self.client.get(reverse("checkin"))
        self.assertEqual(response.status_code, 302)

    def test_customer_cannot_view_another_customers_reservation(self):
        reservation = Reservation.objects.create(
            code="ABCDEFG234", user=self.user, screening=self.screening, quantity=1
        )
        other_user = User.objects.create_user(email="other@example.com", password="Yet-another-secure-2026", email_verified=True)
        self.client.force_login(other_user)
        response = self.client.get(reverse("reservation_detail", args=[reservation.code]))
        self.assertEqual(response.status_code, 404)


class EmailVerificationExpirationTests(TestCase):
    def test_expired_token_does_not_verify_user(self):
        user = User.objects.create_user(email="expiry@example.com", password="A-secure-passphrase-2026")
        token = "expired-token-123"
        verification = EmailVerification.objects.create(
            user=user,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.post(reverse("verify_email", args=[token]))
        self.assertRedirects(response, reverse("login"))
        user.refresh_from_db()
        verification.refresh_from_db()
        self.assertFalse(user.email_verified)
        self.assertIsNone(verification.used_at)
