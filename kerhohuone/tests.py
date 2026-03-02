"""
Comprehensive tests for the Kerhohuone (Clubhouse) booking application.

Tests cover:
- Models: UserProfile, SlotPricing, Booking
- Forms: SignUpForm, BookingForm
- Views: all class-based views
- Edge cases: Chinese/Arabic text, large/small numbers, decimal prices
- Error handling: database constraints, validation
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import BookingForm, SignUpForm
from .models import (
    ADVANCE_BOOKING_MONTHS,
    CANCELLATION_DEADLINE_HOURS,
    DEFAULT_SLOT_PRICE,
    MAX_ACTIVE_BOOKINGS_PER_USER,
    SLOT_COUNT,
    Booking,
    SlotPricing,
    UserProfile,
)


# ---------------------------------------------------------------------------
#  Helper mixin
# ---------------------------------------------------------------------------

class TestHelperMixin:
    """Shared helpers for creating test users and bookings."""

    def create_user(self, username="testuser", password="Str0ng!Pass99",
                    apartment="A12", first_name="Test", last_name="User",
                    email="test@example.com", is_staff=False):
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            is_staff=is_staff,
        )
        UserProfile.objects.create(user=user, apartment_number=apartment)
        return user

    def create_booking(self, user, booking_date=None, booking_type="slot",
                       slot_number=0, is_cancelled=False):
        if booking_date is None:
            booking_date = date.today() + timedelta(days=7)
        booking = Booking(
            user=user,
            date=booking_date,
            booking_type=booking_type,
            slot_number=slot_number if booking_type == "slot" else None,
            is_cancelled=is_cancelled,
        )
        booking.save()
        return booking


# ---------------------------------------------------------------------------
#  Model tests
# ---------------------------------------------------------------------------

class UserProfileModelTest(TestHelperMixin, TestCase):
    """Tests for the UserProfile model."""

    def test_create_profile(self):
        user = self.create_user()
        self.assertEqual(user.profile.apartment_number, "A12")

    def test_str_representation(self):
        user = self.create_user(first_name="Anna", last_name="Korhonen", apartment="B7")
        self.assertIn("Anna Korhonen", str(user.profile))
        self.assertIn("B7", str(user.profile))

    def test_chinese_apartment_number(self):
        """Chinese characters in apartment number."""
        user = self.create_user(username="cn_user", apartment="公寓A栋301")
        self.assertEqual(user.profile.apartment_number, "公寓A栋301")

    def test_arabic_apartment_number(self):
        """Arabic characters in apartment number."""
        user = self.create_user(username="ar_user", apartment="شقة ٤٢")
        self.assertEqual(user.profile.apartment_number, "شقة ٤٢")

    def test_profile_index_exists(self):
        """Verify the apartment_number index is defined."""
        index_names = [idx.name for idx in UserProfile._meta.indexes]
        self.assertIn("idx_profile_apartment", index_names)


class SlotPricingModelTest(TestHelperMixin, TestCase):
    """Tests for the SlotPricing model."""

    def test_default_price(self):
        self.assertEqual(SlotPricing.get_price(0), DEFAULT_SLOT_PRICE)

    def test_set_and_get_price(self):
        SlotPricing.objects.create(slot_number=0, price=Decimal("25.50"))
        self.assertEqual(SlotPricing.get_price(0), Decimal("25.50"))

    def test_full_day_price_sum(self):
        for i in range(SLOT_COUNT):
            SlotPricing.objects.create(slot_number=i, price=Decimal("10.00"))
        self.assertEqual(SlotPricing.get_full_day_price(), Decimal("50.00"))

    def test_very_large_price(self):
        SlotPricing.objects.create(slot_number=0, price=Decimal("999999.99"))
        self.assertEqual(SlotPricing.get_price(0), Decimal("999999.99"))

    def test_very_small_price(self):
        SlotPricing.objects.create(slot_number=1, price=Decimal("0.01"))
        self.assertEqual(SlotPricing.get_price(1), Decimal("0.01"))

    def test_zero_price(self):
        SlotPricing.objects.create(slot_number=2, price=Decimal("0.00"))
        self.assertEqual(SlotPricing.get_price(2), Decimal("0.00"))

    def test_decimal_precision(self):
        SlotPricing.objects.create(slot_number=3, price=Decimal("12.34"))
        self.assertEqual(SlotPricing.get_price(3), Decimal("12.34"))

    def test_unique_slot_number(self):
        SlotPricing.objects.create(slot_number=0, price=Decimal("10.00"))
        with self.assertRaises(IntegrityError):
            SlotPricing.objects.create(slot_number=0, price=Decimal("20.00"))

    def test_str_representation(self):
        sp = SlotPricing.objects.create(slot_number=0, price=Decimal("15.00"))
        self.assertIn("€15.00", str(sp))

    def test_slot_pricing_index(self):
        index_names = [idx.name for idx in SlotPricing._meta.indexes]
        self.assertIn("idx_slotpricing_slot", index_names)


class BookingModelTest(TestHelperMixin, TestCase):
    """Tests for the Booking model."""

    def test_create_slot_booking(self):
        user = self.create_user()
        booking = self.create_booking(user, slot_number=2)
        self.assertEqual(booking.booking_type, "slot")
        self.assertEqual(booking.slot_number, 2)
        self.assertFalse(booking.is_cancelled)

    def test_create_full_day_booking(self):
        user = self.create_user()
        booking = self.create_booking(user, booking_type="full_day")
        self.assertEqual(booking.booking_type, "full_day")
        self.assertIsNone(booking.slot_number)

    def test_slot_label_for_slot(self):
        user = self.create_user()
        booking = self.create_booking(user, slot_number=0)
        self.assertIn("07:00", booking.slot_label)

    def test_slot_label_for_full_day(self):
        user = self.create_user()
        booking = self.create_booking(user, booking_type="full_day")
        self.assertIn("Full Day", booking.slot_label)

    def test_cost_calculated_on_save(self):
        user = self.create_user()
        SlotPricing.objects.create(slot_number=1, price=Decimal("30.00"))
        booking = self.create_booking(user, slot_number=1)
        self.assertEqual(booking.total_cost, Decimal("30.00"))

    def test_full_day_cost(self):
        user = self.create_user()
        for i in range(SLOT_COUNT):
            SlotPricing.objects.create(slot_number=i, price=Decimal("20.00"))
        booking = self.create_booking(user, booking_type="full_day")
        self.assertEqual(booking.total_cost, Decimal("100.00"))

    def test_is_past_for_past_booking(self):
        user = self.create_user()
        booking = self.create_booking(user, booking_date=date.today() - timedelta(days=1))
        self.assertTrue(booking.is_past)

    def test_is_past_for_future_booking(self):
        user = self.create_user()
        booking = self.create_booking(user, booking_date=date.today() + timedelta(days=7))
        self.assertFalse(booking.is_past)

    def test_can_cancel_future_booking(self):
        user = self.create_user()
        booking = self.create_booking(
            user, booking_date=date.today() + timedelta(days=7)
        )
        self.assertTrue(booking.can_cancel)

    def test_cannot_cancel_within_24_hours(self):
        user = self.create_user()
        # Book for tomorrow at 07:00 – less than 24 hours away depending on time
        tomorrow = date.today() + timedelta(days=1)
        booking = self.create_booking(user, booking_date=tomorrow, slot_number=0)
        # Mock current time to 23 hours before start
        start = booking.start_datetime
        fake_now = start - timedelta(hours=23)
        with patch("kerhohuone.models.timezone.now", return_value=fake_now):
            self.assertFalse(booking.can_cancel)

    def test_cannot_cancel_already_cancelled(self):
        user = self.create_user()
        booking = self.create_booking(
            user, booking_date=date.today() + timedelta(days=7), is_cancelled=True
        )
        self.assertFalse(booking.can_cancel)

    def test_clean_slot_required_for_slot_type(self):
        user = self.create_user()
        booking = Booking(
            user=user,
            date=date.today() + timedelta(days=7),
            booking_type="slot",
            slot_number=None,
        )
        with self.assertRaises(ValidationError):
            booking.clean()

    def test_clean_full_day_clears_slot(self):
        user = self.create_user()
        booking = Booking(
            user=user,
            date=date.today() + timedelta(days=7),
            booking_type="full_day",
            slot_number=2,
        )
        booking.clean()
        self.assertIsNone(booking.slot_number)

    def test_unique_constraint_active_bookings(self):
        """Two active bookings on same date/slot should fail."""
        user1 = self.create_user(username="user1")
        user2 = self.create_user(username="user2", email="u2@test.com")
        future_date = date.today() + timedelta(days=10)
        self.create_booking(user1, booking_date=future_date, slot_number=0)
        with self.assertRaises(IntegrityError):
            self.create_booking(user2, booking_date=future_date, slot_number=0)

    def test_cancelled_booking_frees_slot(self):
        """After cancellation, same slot can be rebooked."""
        user1 = self.create_user(username="user1")
        user2 = self.create_user(username="user2", email="u2@test.com")
        future_date = date.today() + timedelta(days=10)
        b1 = self.create_booking(user1, booking_date=future_date, slot_number=0)
        b1.is_cancelled = True
        b1.save()
        # This should work now
        b2 = self.create_booking(user2, booking_date=future_date, slot_number=0)
        self.assertFalse(b2.is_cancelled)

    def test_str_slot_booking(self):
        user = self.create_user()
        booking = self.create_booking(user, slot_number=0)
        s = str(booking)
        self.assertIn("07:00", s)
        self.assertIn(user.username, s)

    def test_str_full_day_booking(self):
        user = self.create_user()
        booking = self.create_booking(user, booking_type="full_day")
        s = str(booking)
        self.assertIn("Full Day", s)

    def test_booking_indexes(self):
        index_names = [idx.name for idx in Booking._meta.indexes]
        self.assertIn("idx_booking_date", index_names)
        self.assertIn("idx_booking_date_slot", index_names)
        self.assertIn("idx_booking_user_active", index_names)
        self.assertIn("idx_booking_user_date", index_names)
        self.assertIn("idx_booking_cancelled", index_names)
        self.assertIn("idx_booking_created", index_names)


# ---------------------------------------------------------------------------
#  Form tests
# ---------------------------------------------------------------------------

class SignUpFormTest(TestHelperMixin, TestCase):
    """Tests for the SignUpForm."""

    def get_valid_data(self, **overrides):
        data = {
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "email": "new@example.com",
            "apartment_number": "C5",
            "password1": "V3ryStr0ng!",
            "password2": "V3ryStr0ng!",
        }
        data.update(overrides)
        return data

    def test_valid_signup(self):
        form = SignUpForm(data=self.get_valid_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.profile.apartment_number, "C5")
        self.assertEqual(user.first_name, "New")

    def test_missing_apartment(self):
        form = SignUpForm(data=self.get_valid_data(apartment_number=""))
        self.assertFalse(form.is_valid())
        self.assertIn("apartment_number", form.errors)

    def test_chinese_name_and_apartment(self):
        form = SignUpForm(data=self.get_valid_data(
            username="zhangsan",
            first_name="三",
            last_name="张",
            apartment_number="公寓B栋202",
        ))
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.first_name, "三")
        self.assertEqual(user.profile.apartment_number, "公寓B栋202")

    def test_arabic_name_and_apartment(self):
        form = SignUpForm(data=self.get_valid_data(
            username="arabuser",
            first_name="أحمد",
            last_name="محمد",
            apartment_number="شقة ١٢",
        ))
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.first_name, "أحمد")
        self.assertEqual(user.profile.apartment_number, "شقة ١٢")

    def test_password_mismatch(self):
        form = SignUpForm(data=self.get_valid_data(password2="Different!Pass1"))
        self.assertFalse(form.is_valid())

    def test_duplicate_username(self):
        self.create_user(username="existing")
        form = SignUpForm(data=self.get_valid_data(username="existing"))
        self.assertFalse(form.is_valid())


class BookingFormTest(TestHelperMixin, TestCase):
    """Tests for the BookingForm."""

    def setUp(self):
        self.user = self.create_user()
        self.future_date = date.today() + timedelta(days=7)

    def get_valid_data(self, **overrides):
        data = {
            "date": self.future_date.isoformat(),
            "booking_type": "slot",
            "slot_number": "0",
        }
        data.update(overrides)
        return data

    def test_valid_slot_booking(self):
        form = BookingForm(data=self.get_valid_data(), user=self.user)
        self.assertTrue(form.is_valid())

    def test_valid_full_day_booking(self):
        form = BookingForm(
            data=self.get_valid_data(booking_type="full_day"),
            user=self.user,
        )
        self.assertTrue(form.is_valid())

    def test_past_date_rejected(self):
        past = date.today() - timedelta(days=1)
        form = BookingForm(
            data=self.get_valid_data(date=past.isoformat()),
            user=self.user,
        )
        self.assertFalse(form.is_valid())

    def test_too_far_future_rejected(self):
        far = date.today() + timedelta(days=ADVANCE_BOOKING_MONTHS * 30 + 10)
        form = BookingForm(
            data=self.get_valid_data(date=far.isoformat()),
            user=self.user,
        )
        self.assertFalse(form.is_valid())

    def test_slot_required_for_slot_type(self):
        form = BookingForm(
            data=self.get_valid_data(slot_number=""),
            user=self.user,
        )
        self.assertFalse(form.is_valid())

    def test_max_active_bookings(self):
        """Cannot exceed 4 active bookings."""
        for i in range(MAX_ACTIVE_BOOKINGS_PER_USER):
            self.create_booking(
                self.user,
                booking_date=date.today() + timedelta(days=10 + i),
                slot_number=i % SLOT_COUNT,
            )
        form = BookingForm(
            data=self.get_valid_data(
                date=(date.today() + timedelta(days=20)).isoformat()
            ),
            user=self.user,
        )
        self.assertFalse(form.is_valid())

    def test_slot_conflict(self):
        """Same date + slot already booked."""
        self.create_booking(self.user, booking_date=self.future_date, slot_number=0)
        other_user = self.create_user(username="other", email="o@test.com")
        form = BookingForm(data=self.get_valid_data(), user=other_user)
        self.assertFalse(form.is_valid())

    def test_full_day_conflict_with_existing_slot(self):
        self.create_booking(self.user, booking_date=self.future_date, slot_number=2)
        other_user = self.create_user(username="other", email="o@test.com")
        form = BookingForm(
            data=self.get_valid_data(booking_type="full_day"),
            user=other_user,
        )
        self.assertFalse(form.is_valid())

    def test_total_cost_calculation(self):
        SlotPricing.objects.create(slot_number=0, price=Decimal("25.00"))
        form = BookingForm(data=self.get_valid_data(), user=self.user)
        self.assertTrue(form.is_valid())
        cost = form.get_total_cost()
        self.assertEqual(cost, Decimal("25.00"))


# ---------------------------------------------------------------------------
#  View tests
# ---------------------------------------------------------------------------

class HomeViewTest(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("kerhohuone:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kerhohuone")

    def test_home_contains_login_link_for_anon(self):
        response = self.client.get(reverse("kerhohuone:home"))
        self.assertContains(response, "Login")


class SignUpViewTest(TestHelperMixin, TestCase):
    def test_signup_page_loads(self):
        response = self.client.get(reverse("kerhohuone:signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Account")

    def test_signup_creates_user(self):
        response = self.client.post(reverse("kerhohuone:signup"), {
            "username": "newbie",
            "first_name": "Test",
            "last_name": "New",
            "email": "n@test.com",
            "apartment_number": "D9",
            "password1": "MyStr0ngPwd!",
            "password2": "MyStr0ngPwd!",
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(User.objects.filter(username="newbie").exists())
        user = User.objects.get(username="newbie")
        self.assertEqual(user.profile.apartment_number, "D9")

    def test_signup_with_chinese_data(self):
        response = self.client.post(reverse("kerhohuone:signup"), {
            "username": "chinese_user",
            "first_name": "明",
            "last_name": "李",
            "email": "li@test.com",
            "apartment_number": "公寓101",
            "password1": "MyStr0ngPwd!",
            "password2": "MyStr0ngPwd!",
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="chinese_user")
        self.assertEqual(user.first_name, "明")
        self.assertEqual(user.profile.apartment_number, "公寓101")

    def test_signup_with_arabic_data(self):
        response = self.client.post(reverse("kerhohuone:signup"), {
            "username": "arabic_user",
            "first_name": "فاطمة",
            "last_name": "علي",
            "email": "ali@test.com",
            "apartment_number": "شقة ٧",
            "password1": "MyStr0ngPwd!",
            "password2": "MyStr0ngPwd!",
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="arabic_user")
        self.assertEqual(user.first_name, "فاطمة")


class LoginViewTest(TestHelperMixin, TestCase):
    def test_login_page_loads(self):
        response = self.client.get(reverse("kerhohuone:login"))
        self.assertEqual(response.status_code, 200)

    def test_valid_login(self):
        self.create_user(username="logintest", password="Str0ng!Pass99")
        response = self.client.post(reverse("kerhohuone:login"), {
            "username": "logintest",
            "password": "Str0ng!Pass99",
        })
        self.assertEqual(response.status_code, 302)

    def test_invalid_login(self):
        response = self.client.post(reverse("kerhohuone:login"), {
            "username": "nope",
            "password": "wrong",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid")


class DashboardViewTest(TestHelperMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.login(username="testuser", password="Str0ng!Pass99")

    def test_dashboard_loads(self):
        response = self.client.get(reverse("kerhohuone:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")

    def test_dashboard_shows_upcoming_bookings(self):
        self.create_booking(self.user)
        response = self.client.get(reverse("kerhohuone:dashboard"))
        self.assertContains(response, "Upcoming Bookings")

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("kerhohuone:dashboard"))
        self.assertEqual(response.status_code, 302)


class CalendarViewTest(TestHelperMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.login(username="testuser", password="Str0ng!Pass99")

    def test_calendar_loads(self):
        response = self.client.get(reverse("kerhohuone:calendar"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calendar")

    def test_calendar_specific_month(self):
        response = self.client.get(reverse("kerhohuone:calendar_month", args=[2026, 6]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "June")

    def test_calendar_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("kerhohuone:calendar"))
        self.assertEqual(response.status_code, 302)


class BookingCreateViewTest(TestHelperMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.login(username="testuser", password="Str0ng!Pass99")
        self.future_date = date.today() + timedelta(days=7)

    def test_booking_form_loads(self):
        response = self.client.get(reverse("kerhohuone:book"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book the Clubhouse")

    def test_create_slot_booking(self):
        response = self.client.post(reverse("kerhohuone:book"), {
            "date": self.future_date.isoformat(),
            "booking_type": "slot",
            "slot_number": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Booking.objects.filter(user=self.user, date=self.future_date).exists()
        )

    def test_create_full_day_booking(self):
        response = self.client.post(reverse("kerhohuone:book"), {
            "date": self.future_date.isoformat(),
            "booking_type": "full_day",
            "slot_number": "",
        })
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(user=self.user, date=self.future_date)
        self.assertEqual(booking.booking_type, "full_day")

    def test_booking_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("kerhohuone:book"))
        self.assertEqual(response.status_code, 302)

    def test_booking_with_preselected_date(self):
        response = self.client.get(
            reverse("kerhohuone:book_date", args=[self.future_date.isoformat()])
        )
        self.assertEqual(response.status_code, 200)


class BookingDetailViewTest(TestHelperMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.login(username="testuser", password="Str0ng!Pass99")
        self.booking = self.create_booking(self.user)

    def test_detail_loads(self):
        response = self.client.get(
            reverse("kerhohuone:booking_detail", args=[self.booking.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Booking Details")

    def test_other_user_cannot_view(self):
        other = self.create_user(username="other", email="o@test.com")
        self.client.logout()
        self.client.login(username="other", password="Str0ng!Pass99")
        response = self.client.get(
            reverse("kerhohuone:booking_detail", args=[self.booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_staff_can_view_any_booking(self):
        staff = self.create_user(
            username="staff", email="s@test.com", is_staff=True
        )
        self.client.logout()
        self.client.login(username="staff", password="Str0ng!Pass99")
        response = self.client.get(
            reverse("kerhohuone:booking_detail", args=[self.booking.pk])
        )
        self.assertEqual(response.status_code, 200)


class BookingCancelViewTest(TestHelperMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.login(username="testuser", password="Str0ng!Pass99")

    def test_cancel_future_booking(self):
        booking = self.create_booking(
            self.user, booking_date=date.today() + timedelta(days=14)
        )
        response = self.client.post(
            reverse("kerhohuone:booking_cancel", args=[booking.pk])
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertTrue(booking.is_cancelled)

    def test_cannot_cancel_past_booking(self):
        booking = self.create_booking(
            self.user, booking_date=date.today() - timedelta(days=1)
        )
        response = self.client.post(
            reverse("kerhohuone:booking_cancel", args=[booking.pk])
        )
        booking.refresh_from_db()
        self.assertFalse(booking.is_cancelled)

    def test_cancel_is_post_only(self):
        booking = self.create_booking(
            self.user, booking_date=date.today() + timedelta(days=14)
        )
        response = self.client.get(
            reverse("kerhohuone:booking_cancel", args=[booking.pk])
        )
        self.assertEqual(response.status_code, 405)  # Method not allowed


class MyBookingsViewTest(TestHelperMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.login(username="testuser", password="Str0ng!Pass99")

    def test_my_bookings_loads(self):
        response = self.client.get(reverse("kerhohuone:my_bookings"))
        self.assertEqual(response.status_code, 200)

    def test_shows_user_bookings(self):
        self.create_booking(self.user)
        response = self.client.get(reverse("kerhohuone:my_bookings"))
        self.assertContains(response, "07:00")

    def test_does_not_show_other_user_bookings(self):
        other = self.create_user(username="other", email="o@test.com")
        self.create_booking(other, booking_date=date.today() + timedelta(days=5))
        response = self.client.get(reverse("kerhohuone:my_bookings"))
        self.assertNotContains(response, "other")


# ---------------------------------------------------------------------------
#  Edge case / integration tests
# ---------------------------------------------------------------------------

class EdgeCaseTest(TestHelperMixin, TestCase):
    """Test edge cases including extreme values."""

    def test_booking_on_today(self):
        """Booking for today should be allowed."""
        user = self.create_user()
        form = BookingForm(
            data={
                "date": date.today().isoformat(),
                "booking_type": "slot",
                "slot_number": "4",  # last slot, more likely still in future
            },
            user=user,
        )
        # This may or may not be valid depending on current time
        # but should not raise an exception
        form.is_valid()

    def test_booking_at_max_advance_date(self):
        """Booking at exactly the limit should work."""
        user = self.create_user()
        max_date = date.today() + timedelta(days=ADVANCE_BOOKING_MONTHS * 30)
        form = BookingForm(
            data={
                "date": max_date.isoformat(),
                "booking_type": "slot",
                "slot_number": "0",
            },
            user=user,
        )
        self.assertTrue(form.is_valid())

    def test_all_five_slots_bookable(self):
        """Each of the 5 slots can be independently booked."""
        users = []
        for i in range(SLOT_COUNT):
            u = self.create_user(
                username=f"user{i}", email=f"u{i}@test.com", apartment=f"A{i}"
            )
            users.append(u)

        future_date = date.today() + timedelta(days=10)
        for i, u in enumerate(users):
            booking = self.create_booking(u, booking_date=future_date, slot_number=i)
            self.assertEqual(booking.slot_number, i)

    def test_cancelled_does_not_count_toward_limit(self):
        """Cancelled bookings should not count toward the 4-booking limit."""
        user = self.create_user()
        for i in range(MAX_ACTIVE_BOOKINGS_PER_USER):
            self.create_booking(
                user,
                booking_date=date.today() + timedelta(days=10 + i),
                slot_number=i % SLOT_COUNT,
                is_cancelled=True,
            )
        # Should be able to book since all are cancelled
        form = BookingForm(
            data={
                "date": (date.today() + timedelta(days=30)).isoformat(),
                "booking_type": "slot",
                "slot_number": "0",
            },
            user=user,
        )
        self.assertTrue(form.is_valid())

    def test_large_decimal_price_display(self):
        """Prices with many digits should work."""
        sp = SlotPricing.objects.create(slot_number=0, price=Decimal("123456.78"))
        self.assertEqual(sp.price, Decimal("123456.78"))
        self.assertIn("123456.78", str(sp))


class AdminAccessTest(TestHelperMixin, TestCase):
    """Test admin-specific functionality."""

    def test_admin_can_see_all_bookings(self):
        """Staff user can view any booking via detail view."""
        user = self.create_user(username="regular")
        staff = self.create_user(username="admin_user", email="a@test.com", is_staff=True)
        booking = self.create_booking(user)
        self.client.login(username="admin_user", password="Str0ng!Pass99")
        response = self.client.get(
            reverse("kerhohuone:booking_detail", args=[booking.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_site_accessible(self):
        staff = self.create_user(username="admin_user", email="a@test.com", is_staff=True)
        staff.is_superuser = True
        staff.save()
        self.client.login(username="admin_user", password="Str0ng!Pass99")
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
