"""
Django admin configuration for the Kerhohuone booking application.
Comprehensive admin interface with search, filters, and inline editing.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Booking, SlotPricing, UserProfile


# --------------------------------------------------------------------------- #
#  Inline for UserProfile on User admin                                        #
# --------------------------------------------------------------------------- #

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Profile"
    verbose_name_plural = "Profile"
    fields = ("apartment_number",)


class UserAdmin(BaseUserAdmin):
    """Extend built-in User admin with the UserProfile inline."""
    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "get_apartment",
        "is_staff",
    )
    list_select_related = ("profile",)

    @admin.display(description="Apartment")
    def get_apartment(self, obj):
        try:
            return obj.profile.apartment_number
        except UserProfile.DoesNotExist:
            return "—"


# Re-register User with the enhanced admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# --------------------------------------------------------------------------- #
#  UserProfile admin                                                           #
# --------------------------------------------------------------------------- #

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "apartment_number")
    search_fields = ("user__username", "user__email", "apartment_number")
    list_filter = ("apartment_number",)
    raw_id_fields = ("user",)


# --------------------------------------------------------------------------- #
#  SlotPricing admin                                                           #
# --------------------------------------------------------------------------- #

@admin.register(SlotPricing)
class SlotPricingAdmin(admin.ModelAdmin):
    list_display = ("slot_number", "get_slot_label", "price")
    list_editable = ("price",)
    ordering = ("slot_number",)

    @admin.display(description="Time Slot")
    def get_slot_label(self, obj):
        return obj.get_slot_number_display()


# --------------------------------------------------------------------------- #
#  Booking admin                                                               #
# --------------------------------------------------------------------------- #

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "date",
        "booking_type",
        "get_slot_label",
        "total_cost",
        "is_cancelled",
        "created_at",
    )
    list_filter = (
        "is_cancelled",
        "booking_type",
        "date",
        "created_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__profile__apartment_number",
    )
    date_hierarchy = "date"
    list_select_related = ("user",)
    readonly_fields = ("created_at", "updated_at", "total_cost")
    raw_id_fields = ("user",)
    list_per_page = 50
    ordering = ("-date", "slot_number")

    @admin.display(description="Time Slot")
    def get_slot_label(self, obj):
        return obj.slot_label

    def get_queryset(self, request):
        """Admins can see all bookings including past ones."""
        return super().get_queryset(request)


# --------------------------------------------------------------------------- #
#  Admin site customisation                                                    #
# --------------------------------------------------------------------------- #

admin.site.site_header = "Kerhohuone – Clubhouse Admin"
admin.site.site_title = "Kerhohuone Admin"
admin.site.index_title = "Booking Management"
