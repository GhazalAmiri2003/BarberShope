from datetime import time, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from barbers.models import Barber
from services.models import Service
from core.models import BusinessHours
from .models import Booking, BarberBlock

User = get_user_model()

class BookingTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(phone="+393331234567", password="test-only-password", first_name="Demo")
        self.other = User.objects.create_user(phone="+393331234568", password="test-only-password")
        self.worker = User.objects.create_user(phone="+393331234569", password="test-only-password", role="barber")
        self.barber = Barber.objects.create(user=self.worker, name="Demo barber")
        self.service = Service.objects.create(name="Haircut", duration_minutes=60, price="20.00")
        self.barber.services.add(self.service)
        self.day = timezone.localdate() + timedelta(days=2)
        BusinessHours.objects.create(day_of_week=self.day.weekday(), open_time=time(9), close_time=time(17))
        self.payload = {"barber": self.barber.pk, "service": self.service.pk,
                        "date": self.day.isoformat(), "start_time": "10:00"}

    def create(self):
        self.client.force_authenticate(self.customer)
        r = self.client.post("/api/bookings/", self.payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["booking_id"]

    def test_anonymous_cannot_book(self):
        self.assertEqual(self.client.post("/api/bookings/", self.payload, format="json").status_code, 401)

    def test_overlap_and_adjacent_slot(self):
        self.create()
        self.payload["start_time"] = "10:30"
        self.assertEqual(self.client.post("/api/bookings/", self.payload, format="json").status_code, 409)
        self.payload["start_time"] = "11:00"
        self.assertEqual(self.client.post("/api/bookings/", self.payload, format="json").status_code, 201)

    def test_end_after_closing(self):
        self.client.force_authenticate(self.customer)
        self.payload["start_time"] = "16:30"
        self.assertEqual(self.client.post("/api/bookings/", self.payload, format="json").status_code, 400)

    def test_blocked_interval(self):
        BarberBlock.objects.create(barber=self.barber, date=self.day, start_time=time(10,30), end_time=time(11))
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post("/api/bookings/", self.payload, format="json").status_code, 409)

    def test_owner_only(self):
        pk = self.create()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/my-bookings/", {"phone": self.customer.phone}).data, [])
        self.assertEqual(self.client.post(f"/api/bookings/{pk}/cancel/").status_code, 403)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(f"/api/bookings/{pk}/cancel/").status_code, 200)

    def test_calendar_private_and_full_duration(self):
        self.create()
        params = {"barber": self.barber.pk, "date": self.day.isoformat()}
        self.assertEqual(self.client.get("/api/calendar/", params).status_code, 403)
        self.client.force_authenticate(self.worker)
        rows = self.client.get("/api/calendar/", params).data
        by_time = {row["time"]: row["status"] for row in rows}
        self.assertEqual(by_time["10:00"], "booked")
        self.assertEqual(by_time["10:30"], "booked")
        self.assertEqual(by_time["11:00"], "available")

    def test_customer_cannot_change_services(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post("/api/services/", {"name": "Test"}, format="json").status_code, 403)

    def test_invalid_date(self):
        self.payload["date"] = "not-a-date"
        self.assertEqual(self.client.get("/api/available-slots/", self.payload).status_code, 400)

    def test_unoffered_service(self):
        self.client.force_authenticate(self.customer)
        self.barber.services.clear()
        self.assertEqual(self.client.post("/api/bookings/", self.payload, format="json").status_code, 400)

    def test_available_slots_exclude_overlap(self):
        self.create()
        self.client.force_authenticate(None)
        rows = self.client.get("/api/available-slots/", self.payload).data
        self.assertNotIn("10:00", rows)
        self.assertNotIn("10:30", rows)
        self.assertIn("11:00", rows)
