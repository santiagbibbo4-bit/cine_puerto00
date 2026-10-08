from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Se requiere un email")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields.get("is_staff") or not extra_fields.get("is_superuser"):
            raise ValueError("El superusuario debe tener permisos de staff y superusuario")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.email


class Program(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicado"

    title = models.CharField("título", max_length=180)
    synopsis = models.TextField("sinopsis", blank=True)
    duration_min = models.PositiveSmallIntegerField("duración (min)", null=True, blank=True)
    age_rating = models.CharField("clasificación", max_length=20, blank=True)
    trailer_youtube_id = models.CharField("ID del tráiler de YouTube", max_length=20, blank=True)
    poster = models.URLField("URL del afiche", blank=True)
    poster_image = models.ImageField("afiche (archivo)", upload_to="afiches/", blank=True)
    release_date = models.DateField("fecha de estreno", null=True, blank=True)
    featured = models.BooleanField("destacado", default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "programa"
        verbose_name_plural = "programas"

    def __str__(self):
        return self.title


class ShortFilm(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="shorts", verbose_name="programa")
    title = models.CharField("título", max_length=180)
    director = models.CharField("dirección", max_length=140, blank=True)
    duration_min = models.PositiveSmallIntegerField("duración (min)", null=True, blank=True)
    synopsis = models.TextField("sinopsis", blank=True)
    sort = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        ordering = ["sort", "id"]
        verbose_name = "cortometraje"
        verbose_name_plural = "cortometrajes"

    def __str__(self):
        return self.title


class Screening(models.Model):
    class Room(models.TextChoices):
        TWO_D = "2D", "Sala 2D"
        FOUR_D = "4D", "Sala 4D"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicada"
        CANCELLED = "cancelled", "Cancelada"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="screenings", verbose_name="programa")
    starts_at = models.DateTimeField("fecha y hora")
    room = models.CharField("sala", max_length=2, choices=Room.choices)
    capacity = models.PositiveIntegerField("capacidad", validators=[MinValueValidator(1)])
    booked_count = models.PositiveIntegerField("entradas reservadas", default=0, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PUBLISHED)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["starts_at", "room"],
                condition=~models.Q(status="cancelled"),
                name="unique_active_screening_time_per_room",
            ),
        ]
        verbose_name = "función"
        verbose_name_plural = "funciones"

    def __str__(self):
        return f"{self.program} · {timezone.localtime(self.starts_at):%d/%m %H:%M} ({self.room})"

    def clean(self):
        super().clean()
        if self.capacity and self.capacity < self.booked_count:
            raise ValidationError({"capacity": "La capacidad no puede ser menor que las entradas ya reservadas."})
        if self.starts_at and self.room and self.status != self.Status.CANCELLED:
            local_start = timezone.localtime(self.starts_at).replace(second=0, microsecond=0)
            existing = Screening.objects.filter(
                starts_at__date=local_start.date(),
                room=self.room,
            ).exclude(status=self.Status.CANCELLED)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if any(
                timezone.localtime(starts_at).replace(second=0, microsecond=0) == local_start
                for starts_at in existing.values_list("starts_at", flat=True)
            ):
                raise ValidationError({"starts_at": f"Ya existe otra función en la Sala {self.room} para ese día y horario."})

    @property
    def remaining(self):
        return max(0, self.capacity - self.booked_count)

    @property
    def booking_state(self):
        if self.status == self.Status.CANCELLED:
            return "cancelled"
        if self.starts_at <= timezone.now() + timedelta(minutes=settings.BOOKING_CUTOFF_MINUTES):
            return "closed"
        if self.remaining <= 0:
            return "sold_out"
        return "open"


class Reservation(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmada"
        CHECKED_IN = "checked_in", "Utilizada"
        CANCELLED = "cancelled", "Cancelada"

    code = models.CharField("código", max_length=10, unique=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reservations", verbose_name="cliente")
    screening = models.ForeignKey(Screening, on_delete=models.PROTECT, related_name="reservations", verbose_name="función")
    quantity = models.PositiveSmallIntegerField("cantidad", validators=[MinValueValidator(1)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    idempotency_key = models.CharField(max_length=40, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="checked_reservations")
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "idempotency_key"], condition=~models.Q(idempotency_key=None), name="unique_user_booking_request"),
        ]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"

    def __str__(self):
        return f"{self.code} · {self.user.email}"


class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LegalPage(models.Model):
    slug = models.SlugField(primary_key=True)
    title = models.CharField(max_length=120)
    body = models.TextField()
    reviewed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "texto legal"
        verbose_name_plural = "textos legales"

    def __str__(self):
        return self.title


class SiteSetting(models.Model):
    key = models.CharField(max_length=80, unique=True)
    value = models.TextField(blank=True)

    class Meta:
        verbose_name = "dato del cine"
        verbose_name_plural = "datos del cine"

    def __str__(self):
        return self.key
