"""
Views for the Kerhohuone (Clubhouse) booking application.
All views use class-based generic views following Django best practices.
"""

import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    DetailView,
    FormView,
    ListView,
    TemplateView,
    View,
)

from .forms import BookingForm, SignUpForm
from .models import (
    ADVANCE_BOOKING_MONTHS,
    SLOT_CHOICES,
    SLOT_COUNT,
    Booking,
    SlotPricing,
)


# --------------------------------------------------------------------------- #
#  Public views                                                                #
# --------------------------------------------------------------------------- #


class HomeView(TemplateView):
    """Landing page."""

    template_name = "kerhohuone/home.html"


# --------------------------------------------------------------------------- #
#  Authentication views                                                        #
# --------------------------------------------------------------------------- #


class SignUpView(FormView):
    """User registration with apartment number."""

    template_name = "kerhohuone/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("kerhohuone:dashboard")

    def form_valid(self, form):
        user = form.save()
        auth_login(self.request, user)
        messages.success(self.request, "Welcome! Your account has been created.")
        return super().form_valid(form)


class LoginView(auth_views.LoginView):
    """Login view – redirects to dashboard which shows booking reminders."""

    template_name = "kerhohuone/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse("kerhohuone:dashboard")


class LogoutView(auth_views.LogoutView):
    """Logout and redirect to home."""

    next_page = reverse_lazy("kerhohuone:home")


# --------------------------------------------------------------------------- #
#  Dashboard                                                                   #
# --------------------------------------------------------------------------- #


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Post-login landing page showing user's active (upcoming) bookings as
    reminders and quick links to calendar / new booking.
    """

    template_name = "kerhohuone/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        active_bookings = Booking.objects.filter(
            user=self.request.user,
            is_cancelled=False,
            date__gte=today,
        ).order_by("date", "slot_number")
        ctx["active_bookings"] = active_bookings
        ctx["active_count"] = active_bookings.count()
        return ctx


# --------------------------------------------------------------------------- #
#  Calendar browsing                                                           #
# --------------------------------------------------------------------------- #


class CalendarView(LoginRequiredMixin, TemplateView):
    """
    Monthly calendar showing slot availability and prices for each day.
    """

    template_name = "kerhohuone/calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        year = self.kwargs.get("year", today.year)
        month = self.kwargs.get("month", today.month)

        # Clamp to valid range
        try:
            first_of_month = date(year, month, 1)
        except ValueError:
            first_of_month = date(today.year, today.month, 1)
            year, month = today.year, today.month

        max_date = today + timedelta(days=ADVANCE_BOOKING_MONTHS * 30)

        # Build calendar weeks
        cal = calendar.Calendar(firstweekday=0)  # Monday first
        month_days = cal.monthdayscalendar(year, month)

        # Fetch all active bookings for this month
        bookings_qs = Booking.objects.filter(
            date__year=year,
            date__month=month,
            is_cancelled=False,
        ).values_list("date", "slot_number", "booking_type")

        booked_map = {}  # date -> set of booked slot numbers
        full_day_dates = set()
        for b_date, b_slot, b_type in bookings_qs:
            if b_type == "full_day":
                full_day_dates.add(b_date)
            else:
                booked_map.setdefault(b_date, set()).add(b_slot)

        # Slot prices
        slot_prices = {}
        for slot_num in range(SLOT_COUNT):
            slot_prices[slot_num] = SlotPricing.get_price(slot_num)

        # Build week data
        weeks = []
        for week in month_days:
            week_data = []
            for day_num in week:
                if day_num == 0:
                    week_data.append(None)
                    continue
                d = date(year, month, day_num)
                is_past = d < today
                is_beyond = d > max_date
                is_full_day = d in full_day_dates
                booked_slots = booked_map.get(d, set())
                available_slots = []
                for slot_num in range(SLOT_COUNT):
                    available_slots.append(
                        {
                            "number": slot_num,
                            "label": dict(SLOT_CHOICES)[slot_num],
                            "price": slot_prices[slot_num],
                            "booked": slot_num in booked_slots or is_full_day,
                        }
                    )
                all_booked = is_full_day or len(booked_slots) >= SLOT_COUNT
                week_data.append(
                    {
                        "day": day_num,
                        "date": d,
                        "date_iso": d.isoformat(),
                        "is_past": is_past,
                        "is_beyond": is_beyond,
                        "is_today": d == today,
                        "slots": available_slots,
                        "all_booked": all_booked,
                        "is_full_day": is_full_day,
                    }
                )
            weeks.append(week_data)

        # Navigation
        prev_month = first_of_month - timedelta(days=1)
        next_month = first_of_month + timedelta(days=32)
        next_month = next_month.replace(day=1)

        ctx.update(
            {
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "weeks": weeks,
                "today": today,
                "prev_year": prev_month.year,
                "prev_month": prev_month.month,
                "next_year": next_month.year,
                "next_month": next_month.month,
                "can_go_prev": first_of_month > today.replace(day=1),
                "can_go_next": next_month
                <= max_date.replace(day=1) + timedelta(days=31),
                "slot_prices": slot_prices,
                "slot_choices": SLOT_CHOICES,
                "full_day_price": SlotPricing.get_full_day_price(),
            }
        )
        return ctx


# --------------------------------------------------------------------------- #
#  Booking CRUD                                                                #
# --------------------------------------------------------------------------- #


class BookingCreateView(LoginRequiredMixin, FormView):
    """Create a new booking."""

    template_name = "kerhohuone/book.html"
    form_class = BookingForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        selected_date = self.kwargs.get("selected_date")
        if selected_date:
            initial["date"] = selected_date
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Pass pricing info to template
        slot_prices = {}
        for slot_num in range(SLOT_COUNT):
            slot_prices[slot_num] = str(SlotPricing.get_price(slot_num))
        ctx["slot_prices"] = slot_prices
        ctx["slot_choices"] = SLOT_CHOICES
        ctx["full_day_price"] = str(SlotPricing.get_full_day_price())
        return ctx

    def form_valid(self, form):
        booking_type = form.cleaned_data["booking_type"]
        booking_date = form.cleaned_data["date"]
        slot_number = form.cleaned_data.get("slot_number")

        if booking_type == "full_day":
            # Create bookings for all slots
            booking = Booking.objects.create(
                user=self.request.user,
                date=booking_date,
                booking_type="full_day",
                slot_number=None,
            )
        else:
            booking = Booking.objects.create(
                user=self.request.user,
                date=booking_date,
                booking_type="slot",
                slot_number=int(slot_number),
            )

        messages.success(
            self.request,
            f"Booking confirmed for {booking_date} – {booking.slot_label}. "
            f"Total cost: €{booking.total_cost}",
        )
        return redirect("kerhohuone:booking_detail", pk=booking.pk)


class BookingDetailView(LoginRequiredMixin, DetailView):
    """View details of a single booking."""

    model = Booking
    template_name = "kerhohuone/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs


class BookingCancelView(LoginRequiredMixin, View):
    """Cancel a booking (POST only)."""

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)

        if not booking.can_cancel:
            messages.error(
                request,
                "This booking cannot be cancelled. "
                "Cancellations must be made at least 24 hours before the booking start.",
            )
            return redirect("kerhohuone:booking_detail", pk=pk)

        booking.is_cancelled = True
        booking.save()
        messages.success(request, "Booking cancelled successfully.")
        return redirect("kerhohuone:my_bookings")


class MyBookingsView(LoginRequiredMixin, ListView):
    """List all bookings for the current user."""

    model = Booking
    template_name = "kerhohuone/my_bookings.html"
    context_object_name = "bookings"
    paginate_by = 20

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).order_by(
            "-date", "slot_number"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_count"] = Booking.objects.filter(
            user=self.request.user, is_cancelled=False, date__gte=date.today()
        ).count()
        return ctx
