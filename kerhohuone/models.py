"""
Models for the Kerhohuone (Clubhouse) booking application.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# --- Constants ---
OPENING_HOUR = 7   # 7:00 AM
CLOSING_HOUR = 22  # 10:00 PM
SLOT_DURATION_HOURS = 3
MAX_ACTIVE_BOOKINGS_PER_USER = 4
ADVANCE_BOOKING_MONTHS = 6
CANCELLATION_DEADLINE_HOURS = 24
DEFAULT_SLOT_PRICE = Decimal("0.00")

SLOT_CHOICES = [
    (0, "07:00 – 10:00"),
    (1, "10:00 – 13:00"),
    (2, "13:00 – 16:00"),
    (3, "16:00 – 19:00"),
    (4, "19:00 – 22:00"),
]

SLOT_START_HOURS = {
    0: 7,
    1: 10,
    2: 13,
    3: 16,
    4: 19,
}

SLOT_COUNT = len(SLOT_CHOICES)

BOOKING_TYPE_CHOICES = [
    ("slot", "Single Slot (3 hours)"),
    ("full_day", "Full Day (07:00 – 22:00)"),
]


class UserProfile(models.Model):
    """
    Extended user profile storing the apartment number.
    Linked one-to-one with the Django auth User model.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    apartment_number = models.CharField(
        max_length=20,
        help_text="Apartment number (e.g. A12, B3, 101).",
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        indexes = [
            models.Index(fields=["apartment_number"], name="idx_profile_apartment"),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} – Apt {self.apartment_number}"


class SlotPricing(models.Model):
    """
    Admin-configurable pricing for each time slot.
    One row per slot number (0-4). If no row exists the default price is used.
    """

    slot_number = models.IntegerField(
        choices=SLOT_CHOICES,
        unique=True,
        help_text="The time-slot index (0-4).",
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=DEFAULT_SLOT_PRICE,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Price in EUR for this slot.",
    )

    class Meta:
        verbose_name = "Slot Pricing"
        verbose_name_plural = "Slot Pricings"
        ordering = ["slot_number"]
        indexes = [
            models.Index(fields=["slot_number"], name="idx_slotpricing_slot"),
        ]

    def __str__(self):
        return f"{self.get_slot_number_display()} – €{self.price}"

    @classmethod
    def get_price(cls, slot_number):
        """Return the price for a given slot, or the default."""
        try:
            return cls.objects.get(slot_number=slot_number).price
        except cls.DoesNotExist:
            return DEFAULT_SLOT_PRICE

    @classmethod
    def get_full_day_price(cls):
        """Sum of all individual slot prices for a full day."""
        total = Decimal("0.00")
        for slot_num in range(SLOT_COUNT):
            total += cls.get_price(slot_num)
        return total


class Booking(models.Model):
    """
    A clubhouse booking for a specific date, either a single slot or full day.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    date = models.DateField(
        help_text="Date of the booking.",
    )
    booking_type = models.CharField(
        max_length=10,
        choices=BOOKING_TYPE_CHOICES,
        default="slot",
    )
    slot_number = models.IntegerField(
        choices=SLOT_CHOICES,
        null=True,
        blank=True,
        help_text="Required for single-slot bookings (0-4). Null for full-day.",
    )
    total_cost = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total cost at time of booking.",
    )
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        ordering = ["date", "slot_number"]
        indexes = [
            models.Index(fields=["user", "is_cancelled"], name="idx_booking_user_active"),
            models.Index(fields=["date"], name="idx_booking_date"),
            models.Index(fields=["date", "slot_number"], name="idx_booking_date_slot"),
            models.Index(fields=["user", "date"], name="idx_booking_user_date"),
            models.Index(fields=["is_cancelled"], name="idx_booking_cancelled"),
            models.Index(fields=["created_at"], name="idx_booking_created"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "slot_number"],
                condition=models.Q(is_cancelled=False),
                name="unique_active_date_slot",
            ),
        ]

    def __str__(self):
        if self.booking_type == "full_day":
            return f"{self.date} – Full Day – {self.user.username}"
        slot_label = dict(SLOT_CHOICES).get(self.slot_number, "?")
        return f"{self.date} – {slot_label} – {self.user.username}"

    @property
    def slot_label(self):
        if self.booking_type == "full_day":
            return "Full Day (07:00 – 22:00)"
        return dict(SLOT_CHOICES).get(self.slot_number, "Unknown")

    @property
    def start_datetime(self):
        """Return the timezone-aware start datetime of this booking."""
        if self.booking_type == "full_day":
            hour = OPENING_HOUR
        else:
            hour = SLOT_START_HOURS.get(self.slot_number, OPENING_HOUR)
        return timezone.make_aware(
            timezone.datetime(self.date.year, self.date.month, self.date.day, hour, 0)
        )

    @property
    def is_past(self):
        return self.start_datetime < timezone.now()

    @property
    def can_cancel(self):
        """User can cancel only if start is >24 h away and not already cancelled."""
        if self.is_cancelled:
            return False
        deadline = self.start_datetime - timedelta(hours=CANCELLATION_DEADLINE_HOURS)
        return timezone.now() < deadline

    def clean(self):
        """Model-level validation."""
        super().clean()

        if self.booking_type == "slot" and self.slot_number is None:
            raise ValidationError("Slot number is required for single-slot bookings.")

        if self.booking_type == "full_day":
            self.slot_number = None

    def calculate_cost(self):
        """Calculate and return the total cost based on current pricing."""
        if self.booking_type == "full_day":
            return SlotPricing.get_full_day_price()
        return SlotPricing.get_price(self.slot_number)

    def save(self, *args, **kwargs):
        self.total_cost = self.calculate_cost()
        super().save(*args, **kwargs)
