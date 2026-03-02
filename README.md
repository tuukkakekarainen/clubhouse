# Kerhohuone – Clubhouse Booking System

A Django web application for booking a shared clubhouse. Built with Django 5.2, SQLite3, and responsive HTML/CSS with WCAG 2.1 compliant contrast in both light and dark modes.

## Features

### User Authentication
- **Sign up** with username, name, email, and mandatory apartment number
- **Login / Logout** with automatic redirect to dashboard
- Post-login **booking reminders** showing all upcoming reservations

### Calendar Browsing
- **Monthly calendar view** with slot availability at a glance
- Color-coded slots: green = available, red = booked
- **Prices displayed directly on each available slot**
- Navigate months forward/backward (up to 6 months ahead)
- Click an available slot to jump directly to the booking form

### Booking System
- **Book by slot** (3-hour blocks) or **full day** (07:00–22:00)
- 5 daily slots: `07:00–10:00`, `10:00–13:00`, `13:00–16:00`, `16:00–19:00`, `19:00–22:00`
- Cannot book in the past
- Book up to **6 months in advance**
- Maximum **4 active bookings** per user
- **Total cost calculated and displayed** before confirmation
- Unique constraint prevents double-booking

### Cancellation
- Cancel bookings **at least 24 hours before** the reserved start time
- Cancelled bookings free the slot for others
- Cancelled bookings don't count toward the 4-booking limit

### Pricing
- Admin-configurable **per-slot pricing**
- Prices displayed on calendar slots and in the booking form
- Full-day price = sum of all 5 individual slot prices
- Supports decimal EUR amounts (e.g., €12.50)

### Admin Interface
- Full Django admin with custom headers
- **Booking management**: search by user, email, apartment; filter by status, date, type; date hierarchy
- **User management**: inline apartment number display and editing
- **Slot pricing**: editable list with all 5 slots
- Staff can view **past bookings** and any user's booking details

### Design
- Responsive layout (mobile-friendly)
- **Light mode** (default) and **dark mode** via toggle button
- WCAG 2.1 AA compliant contrast ratios
- Clean typography using system fonts (Segoe UI / system-ui)

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 2. Install Django
pip install django

# 3. Run migrations
python manage.py migrate

# 4. Create a superuser (admin)
python manage.py createsuperuser

# 5. Start the development server
python manage.py runserver

# 6. Open in browser
# http://127.0.0.1:8000/         – Home page
# http://127.0.0.1:8000/admin/   – Admin interface
```

## Usage Examples

### Register a New Account
1. Go to `/signup/`
2. Fill in username, name, email, apartment number (e.g., "A12"), and password
3. You're automatically logged in and redirected to your dashboard

### Book a Slot
1. Go to **Calendar** → click an available (green) slot
2. Or go to **Book** → select date, type (slot or full day), and time slot
3. Review the total cost → click **Confirm Booking**

### Cancel a Booking
1. Go to **My Bookings** or **Dashboard**
2. Click **Cancel** next to any booking (if >24 hours before start)

### Admin: Set Slot Prices
1. Login to `/admin/` as a superuser
2. Go to **Slot Pricings**
3. Edit the price for each of the 5 time slots

## Database Indexes

Optimized for common queries:

| Index | Purpose |
|-------|---------|
| `idx_booking_date` | Calendar view – fetch bookings by date |
| `idx_booking_date_slot` | Availability check – date + slot lookup |
| `idx_booking_user_active` | Dashboard – user's active bookings |
| `idx_booking_user_date` | My bookings – user's bookings by date |
| `idx_booking_cancelled` | Filter active vs cancelled |
| `idx_booking_created` | Admin – sort by creation date |
| `idx_profile_apartment` | Search by apartment number |
| `idx_slotpricing_slot` | Price lookup by slot |

## Running Tests

```bash
python manage.py test kerhohuone -v2
```

84 tests covering models, forms, views, edge cases (Chinese/Arabic text, extreme numbers), and admin access.

## Tech Stack

- **Django 5.2** – Python web framework
- **SQLite3** – Database
- **HTML/CSS** – No external dependencies, fully self-contained templates
- **JavaScript** – Minimal (theme toggle, dynamic price display)
