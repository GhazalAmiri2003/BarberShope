# Salon Booking Backend

A modular Django REST API for managing salon appointments, barber schedules, service durations and business hours. The repository includes a minimal browser-based API demo, not a complete production frontend.

## Architecture

| Django app | Responsibility |
| --- | --- |
| users | Phone-based accounts, password validation, JWT login and refresh |
| barbers | Barber profiles and offered services |
| services | Service catalogue, duration and pricing |
| core | Business opening hours and permission helpers |
| booking | Availability, appointment creation/cancellation, time blocks and calendars |

**Stack:** Python, Django 5.2 LTS, Django REST Framework, Simple JWT, SQLite, HTML/JavaScript.

## Scheduling

Availability uses a 30-minute start grid anchored to opening time, but reserves the full duration of each service. Intervals overlap when start A < end B and end A > start B, allowing adjacent appointments. Booking creation validates opening hours, future time, active barber and offered service, and checks both appointments and blocked intervals inside a transaction. SQLite IMMEDIATE transactions serialize writers; scheduling mutations also lock the stable barber row on databases that support row locking. Production concurrency and alternative database deployments still require testing.

Times are interpreted in the configured business timezone (default Europe/Rome). Overnight opening hours are not supported.

## Access control

- Public: active catalogue and availability; registration/login.
- Customers: create, list and cancel their own appointments using JWT.
- Barbers: manage their own calendar, blocks and cancellations.
- Staff: manage catalogue/hours and all barber schedules.
- Django admin booking/block records are read-only to avoid bypassing scheduling rules.

Customer ownership uses a foreign key, not a supplied phone number. Legacy bookings remain unassigned after migration; staff must verify ownership before any manual reassignment. Registration does not verify possession of a phone number. SMS verification, distributed rate limiting, production deployment security and load testing are future work.

## Run locally

Python 3.10+ required. The original project was generated with Django 6.0; dependencies are now scoped to Django 5.2 LTS for compatibility with the selected REST/JWT packages. Runtime compatibility still needs verification.

```bash
python -m venv .venv
# Activate the environment for your operating system.
python -m pip install -r requirements.txt
```

Copy .env.example to .env and set DJANGO_SECRET_KEY to a fresh random value. Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Use /admin/ to create a user with the barber role (or register a demo user and assign the role as staff), a barber profile, offered services and opening hours. Register a separate customer through the API. Keep real customer data and .env out of source control. To use testB.html, serve this directory locally at port 5500 using `python -m http.server 5500 --bind 127.0.0.1` in a separate terminal, then open http://127.0.0.1:5500/testB.html. Use a clean demo checkout without private files when serving static content.

## API examples

All paths are under /api/. Protected requests use Authorization: Bearer <access token>.

| Method | Endpoint |
| --- | --- |
| POST | auth/register/, auth/login/, auth/refresh/ |
| GET | barbers/, services/, business-hours/ |
| GET | available-slots/?barber=1&service=1&date=YYYY-MM-DD |
| POST | bookings/ |
| GET | my-bookings/ |
| POST | bookings/{id}/cancel/ |
| GET | calendar/?barber=1&date=YYYY-MM-DD |
| GET | barber-bookings/?barber=1 |
| POST | block-time/ |
| DELETE | block/{id}/ |

Booking JSON: {"barber": 1, "service": 1, "date": "YYYY-MM-DD", "start_time": "10:00"}.
The API derives the customer phone from the authenticated account.

## Tests

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Tests cover ownership, permissions, interval overlap, adjacent appointments, closing hours, blocked intervals, malformed dates and calendar duration. Tests are added but have not been independently executed at the time of this update. No production readiness claim is made.
