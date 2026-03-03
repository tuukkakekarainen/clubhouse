"""
URL configuration for the kerhohuone app.
"""

from django.urls import path

from . import views

app_name = "kerhohuone"

urlpatterns = [
    # Public
    path("", views.HomeView.as_view(), name="home"),
    # Auth
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    # Dashboard (shows active bookings after login)
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # Calendar browsing
    path("calendar/", views.CalendarView.as_view(), name="calendar"),
    path(
        "calendar/<int:year>/<int:month>/",
        views.CalendarView.as_view(),
        name="calendar_month",
    ),
    # Booking
    path("book/", views.BookingCreateView.as_view(), name="book"),
    path(
        "book/<str:selected_date>/", views.BookingCreateView.as_view(), name="book_date"
    ),
    path("booking/<int:pk>/", views.BookingDetailView.as_view(), name="booking_detail"),
    path(
        "booking/<int:pk>/cancel/",
        views.BookingCancelView.as_view(),
        name="booking_cancel",
    ),
    # My bookings
    path("my-bookings/", views.MyBookingsView.as_view(), name="my_bookings"),
]
