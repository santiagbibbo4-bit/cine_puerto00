from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import Program, Screening, ShortFilm, User


class RegistrationForm(UserCreationForm):
    accept_terms = forms.BooleanField(
        label="Acepto los términos y condiciones y la política de privacidad.",
        required=True,
    )

    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ReservationForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=100)
    key = forms.CharField(max_length=40, min_length=10, widget=forms.HiddenInput)


class CheckInForm(forms.Form):
    code = forms.CharField(max_length=24, label="Código de reserva")


class ProgramManagementForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = (
            "title",
            "synopsis",
            "duration_min",
            "age_rating",
            "trailer_youtube_id",
            "poster_image",
            "poster",
            "release_date",
            "featured",
            "status",
        )
        widgets = {
            "synopsis": forms.Textarea(attrs={"rows": 4}),
            "release_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "poster_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "featured": forms.CheckboxInput(),
        }
        help_texts = {
            "release_date": "Si es futura y el programa está publicado, aparece en Próximos estrenos.",
            "featured": "Si lo marcás, aparece destacado en el carrusel de Inicio.",
            "status": "Al publicar aparece en el sitio. Para que aparezca en Cartelera, agregá al menos una función publicada.",
            "poster": "Opcional: enlace a una imagen si preferís no subir un archivo.",
        }

    def clean_poster_image(self):
        image = self.cleaned_data.get("poster_image")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La imagen no puede superar los 5 MB.")
        return image


class ScreeningManagementForm(forms.ModelForm):
    class Meta:
        model = Screening
        fields = ("starts_at", "room", "capacity", "status")
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.instance.pk:
            self.initial.setdefault("status", Screening.Status.PUBLISHED)


class ScreeningManagementFormSetBase(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        excluded_ids = [form.instance.pk for form in self.forms if form.instance.pk]
        occupied = set()
        for form in self.forms:
            data = getattr(form, "cleaned_data", {})
            if not data or data.get("DELETE"):
                continue
            starts_at = data.get("starts_at")
            room = data.get("room")
            if not starts_at or not room or data.get("status") == Screening.Status.CANCELLED:
                continue

            local_start = timezone.localtime(starts_at).replace(second=0, microsecond=0)
            slot = (local_start, room)
            existing_starts = Screening.objects.filter(
                starts_at__date=local_start.date(), room=room
            ).exclude(pk__in=excluded_ids).exclude(status=Screening.Status.CANCELLED).values_list(
                "starts_at", flat=True
            )
            existing_conflict = any(
                timezone.localtime(existing_start).replace(second=0, microsecond=0) == local_start
                for existing_start in existing_starts
            )
            if slot in occupied or existing_conflict:
                form.add_error(
                    None,
                    f"Ya existe otra función en la Sala {room} para ese día y horario.",
                )
            occupied.add(slot)


ScreeningManagementFormSet = inlineformset_factory(
    Program,
    Screening,
    form=ScreeningManagementForm,
    formset=ScreeningManagementFormSetBase,
    extra=0,
    can_delete=True,
    max_num=1000,
    validate_max=False,
)

ShortFilmManagementFormSet = inlineformset_factory(
    Program,
    ShortFilm,
    fields=("title", "director", "duration_min", "synopsis", "sort"),
    extra=2,
    can_delete=True,
    max_num=30,
    validate_max=True,
    widgets={"synopsis": forms.Textarea(attrs={"rows": 2})},
)
