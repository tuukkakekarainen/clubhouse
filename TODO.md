# TODO – Kerhohuone Clubhouse Booking

## Completed ✅
- [x] User authentication (login, logout, sign up with apartment number)
- [x] Calendar browsing with monthly navigation
- [x] Slot booking (3-hour slots) and full-day booking
- [x] 5 daily slots: 07:00–10:00, 10:00–13:00, 13:00–16:00, 16:00–19:00, 19:00–22:00
- [x] Maximum 4 active bookings per user
- [x] Cannot book in the past or more than 6 months ahead
- [x] 24-hour cancellation policy
- [x] Admin-configurable per-slot pricing
- [x] Prices displayed on calendar and booking form
- [x] Total cost calculation and display
- [x] Post-login dashboard with booking reminders
- [x] Comprehensive Django admin interface
- [x] Responsive design with dark/light mode toggle
- [x] WCAG 2.1 compliant contrast
- [x] Database indexes for all common queries
- [x] 84 comprehensive tests (Chinese/Arabic text, edge cases)

## To Implement 📋

### High Priority
- [ ] Email notifications for booking confirmations and cancellations
- [ ] Password reset via email
- [ ] Recurring/repeat bookings
- [ ] Booking history export (CSV/PDF)

### Medium Priority
- [ ] Payment integration (e.g., Stripe)
- [ ] Booking approval workflow (admin approves before confirmed)
- [ ] Waitlist when slots are fully booked
- [ ] User profile editing (change apartment, email, password)
- [ ] Multi-language support (Finnish, English, Swedish)

### Low Priority
- [ ] iCal/Google Calendar integration
- [ ] REST API for mobile app
- [ ] Booking analytics dashboard for admins
- [ ] Seasonal pricing (different rates for weekends/holidays)
- [ ] Terms and conditions acceptance
- [ ] Rate limiting for booking attempts
- [ ] Accessibility audit with screen readers

### Technical Debt
- [ ] Move secret key to environment variable
- [ ] Add CSRF protection logging
- [ ] Add request rate limiting middleware
- [ ] Set up continuous integration (CI)
- [ ] Static file collection and CDN setup for production
- [ ] Database backup strategy
- [ ] Logging configuration
