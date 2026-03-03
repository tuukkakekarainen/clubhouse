"""
Forms for the Kerhohuone booking application.
"""

from datetime import date, timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import models as db_models

from .models import (
    ADVANCE_BOOKING_MONTHS,
    BOOKING_TYPE_CHOICES,
    MAX_ACTIVE_BOOKINGS_PER_USER,
    SLOT_CHOICES,
    Booking,
    SlotPricing,
    UserProfile,
)


class SignUpForm(UserCreationForm):
    """Registration form that also collects apartment number."""

    apartment_number = forms.CharField(
        max_length=20,
        required=True,
        help_text="Your apartment number (e.g. A12, B3, 101).",
        widget=forms.TextInput(
            attrs={"placeholder": "Apartment number", "autofocus": True}
        ),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Last name"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "Email address"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "apartment_number",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                apartment_number=self.cleaned_data["apartment_number"],
            )
        return user


class BookingForm(forms.Form):
    """Form for creating a new booking."""

    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Select a date for your booking.",
    )
    booking_type = forms.ChoiceField(
        choices=BOOKING_TYPE_CHOICES,
        initial="slot",
        widget=forms.RadioSelect,
    )
    slot_number = forms.ChoiceField(
        choices=[("", "— Select a slot —")] + SLOT_CHOICES,
        required=False,
        help_text="Required when booking a single slot.",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Set min/max dates
        today = date.today()
        max_date = today + timedelta(days=ADVANCE_BOOKING_MONTHS * 30)
        self.fields["date"].widget.attrs["min"] = today.isoformat()
        self.fields["date"].widget.attrs["max"] = max_date.isoformat()

    def clean_date(self):
        booking_date = self.cleaned_data["date"]
        today = date.today()
        max_date = today + timedelta(days=ADVANCE_BOOKING_MONTHS * 30)

        if booking_date < today:
            raise forms.ValidationError("You cannot book in the past.")
        if booking_date > max_date:
            raise forms.ValidationError(
                f"You can only book up to {ADVANCE_BOOKING_MONTHS} months in advance."
            )
        return booking_date

    def clean(self):
        cleaned = super().clean()
        booking_type = cleaned.get("booking_type")
        slot_number = cleaned.get("slot_number")
        booking_date = cleaned.get("date")

        if not booking_date:
            return cleaned

        # Validate slot selection
        if booking_type == "slot":
            if not slot_number and slot_number != 0:
                raise forms.ValidationError("Please select a time slot.")
            slot_number = int(slot_number)
            cleaned["slot_number"] = slot_number
        else:
            cleaned["slot_number"] = None

        # Check max active bookings
        if self.user:
            active_count = Booking.objects.filter(
                user=self.user, is_cancelled=False
            ).count()
            if active_count >= MAX_ACTIVE_BOOKINGS_PER_USER:
                raise forms.ValidationError(
                    f"You already have {MAX_ACTIVE_BOOKINGS_PER_USER} active bookings. "
                    "Please cancel an existing booking first."
                )

        # Check availability
        if booking_type == "slot":
            conflict = (
                Booking.objects.filter(
                    date=booking_date,
                    is_cancelled=False,
                )
                .filter(
                    db_models.Q(slot_number=slot_number)
                    | db_models.Q(booking_type="full_day")
                )
                .exists()
            )
            if conflict:
                raise forms.ValidationError("This slot is already booked.")
        elif booking_type == "full_day":
            conflict = Booking.objects.filter(
                date=booking_date,
                is_cancelled=False,
            ).exists()
            if conflict:
                raise forms.ValidationError(
                    "Cannot book full day — one or more slots are already taken."
                )

        return cleaned

    def get_total_cost(self):
        """Return the cost for the selected booking."""
        booking_type = self.cleaned_data.get("booking_type")
        slot_number = self.cleaned_data.get("slot_number")
        if booking_type == "full_day":
            return SlotPricing.get_full_day_price()
        if slot_number is not None:
            return SlotPricing.get_price(int(slot_number))
        return SlotPricing.get_price(0)
