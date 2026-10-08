from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import EmailVerification, LegalPage, Program, Reservation, Screening, ShortFilm, SiteSetting, User

admin.site.site_header = "Administración · Cine de Cortos"
admin.site.site_title = "Cine de Cortos"
admin.site.index_title = "Gestión del cine"


class ShortFilmInline(admin.TabularInline):
    model = ShortFilm
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "featured", "release_date")
    list_filter = ("status", "featured")
    search_fields = ("title", "synopsis")
    inlines = [ShortFilmInline]
    fieldsets = (
        ("Información", {"fields": ("title", "synopsis", "duration_min", "age_rating", "trailer_youtube_id")}),
        ("Afiche y publicación", {"fields": ("poster_image", "poster", "release_date", "featured", "status")}),
    )


@admin.register(Screening)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = ("program", "starts_at", "room", "capacity", "booked_count", "status")
    list_filter = ("room", "status")
    search_fields = ("program__title",)
    readonly_fields = ("booked_count",)
    fields = ("program", "starts_at", "room", "capacity", "booked_count", "status")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("code", "user", "screening", "quantity", "status", "created_at")
    list_filter = ("status", "screening__room")
    search_fields = ("code", "user__email", "screening__program__title")
    readonly_fields = ("code", "user", "screening", "quantity", "status", "idempotency_key", "created_at", "checked_in_at", "checked_in_by", "email_sent_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class CineUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)


class CineUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CineUserCreationForm
    form = CineUserChangeForm
    ordering = ("email",)
    list_display = ("email", "email_verified", "is_staff", "is_active")
    list_filter = ("email_verified", "is_staff", "is_active")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Verificación", {"fields": ("email_verified",)}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff", "is_superuser")}),)


admin.site.register(LegalPage)
admin.site.register(SiteSetting)
admin.site.register(EmailVerification)
