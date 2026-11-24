from datetime import datetime, timedelta
from django.db import transaction, OperationalError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from core.permissions import is_manager, manages_barber
from core.models import BusinessHours
from barbers.models import Barber
from services.models import Service
from .models import Booking, BarberBlock

STEP = timedelta(minutes=30)

class DayInput(serializers.Serializer):
    barber = serializers.IntegerField(min_value=1)
    date = serializers.DateField()

class SlotInput(DayInput):
    service = serializers.IntegerField(min_value=1)

class BookingInput(SlotInput):
    start_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    customer_name = serializers.CharField(max_length=100, required=False)

class BlockInput(DayInput):
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True)

def parse(cls, data):
    s = cls(data=data)
    s.is_valid(raise_exception=True)
    return s.validated_data

def hours_for(day):
    rows = list(BusinessHours.objects.filter(day_of_week=day.weekday())[:2])
    if len(rows) != 1 or rows[0].is_closed or rows[0].open_time >= rows[0].close_time:
        return None
    return rows[0]

def bounds(day, hours):
    return datetime.combine(day, hours.open_time), datetime.combine(day, hours.close_time)

def starts(day, hours):
    current, close = bounds(day, hours)
    while current < close:
        yield current
        current += STEP

def future(moment):
    return moment > timezone.localtime().replace(tzinfo=None)

def eligible(barber, service):
    if not barber.is_active or not service.is_active or not barber.services.filter(pk=service.pk).exists():
        raise ValidationError("Service is not offered by this active barber")
    if not 0 < service.duration_minutes < 1440:
        raise ValidationError("Invalid service duration")

def overlaps(start, end, other_start, other_end):
    return start < other_end and end > other_start

def intervals(barber, day):
    bookings = Booking.objects.filter(barber=barber, date=day, status="booked")
    blocks = BarberBlock.objects.filter(barber=barber, date=day)
    return bookings, blocks

def conflicting(barber, day, start, end):
    return any(q.filter(start_time__lt=end, end_time__gt=start).exists() for q in intervals(barber, day))

def locked_barber(pk):
    # Stable parent row, including when no reservations yet exist.
    # SQLite serializes writers using IMMEDIATE transactions in settings.
    return get_object_or_404(Barber.objects.select_for_update(), pk=pk)

def busy():
    return Response({"error": "Database busy; retry shortly"}, status=503)

@api_view(["GET"])
@permission_classes([AllowAny])
def available_slots(request):
    data = parse(SlotInput, request.query_params)
    barber = get_object_or_404(Barber, pk=data["barber"])
    service = get_object_or_404(Service, pk=data["service"])
    eligible(barber, service)
    day = data["date"]
    hours = hours_for(day)
    if not hours:
        return Response([])
    bookings, blocks = intervals(barber, day)
    occupied = list(bookings.values_list("start_time", "end_time")) + list(blocks.values_list("start_time", "end_time"))
    _, close = bounds(day, hours)
    result = []
    for start in starts(day, hours):
        end = start + timedelta(minutes=service.duration_minutes)
        if end <= close and future(start) and not any(overlaps(start.time(), end.time(), a, b) for a, b in occupied):
            result.append(start.strftime("%H:%M"))
    return Response(result)

@api_view(["POST"])
def create_booking(request):
    data = parse(BookingInput, request.data)
    if request.user.role != "customer":
        raise PermissionDenied("Customer account required")
    try:
        with transaction.atomic():
            barber = locked_barber(data["barber"])
            service = get_object_or_404(Service, pk=data["service"])
            eligible(barber, service)
            day = data["date"]
            start = datetime.combine(day, data["start_time"])
            end = start + timedelta(minutes=service.duration_minutes)
            hours = hours_for(day)
            if not hours or start not in starts(day, hours) or end > bounds(day, hours)[1] or not future(start):
                raise ValidationError("Select a future slot within opening hours on the 30-minute grid")
            if conflicting(barber, day, start.time(), end.time()):
                return Response({"error": "Slot unavailable"}, status=409)
            booking = Booking.objects.create(barber=barber, service=service, customer=request.user,
                date=day, start_time=start.time(), end_time=end.time(),
                customer_name=data.get("customer_name") or request.user.first_name or "Customer",
                customer_phone=request.user.phone)
        return Response({"booking_id": booking.pk}, status=201)
    except OperationalError:
        return busy()

@api_view(["POST"])
def cancel_booking(request, booking_id):
    try:
        with transaction.atomic():
            booking = get_object_or_404(Booking.objects.select_related("barber"), pk=booking_id)
            if booking.customer_id != request.user.pk and not manages_barber(request.user, booking.barber):
                raise PermissionDenied()
            locked_barber(booking.barber_id)
            booking = get_object_or_404(Booking, pk=booking_id)
            booking.status = "cancelled"
            booking.save(update_fields=["status"])
        return Response({"message": "booking cancelled"})
    except OperationalError:
        return busy()

@api_view(["POST"])
def block_time(request):
    data = parse(BlockInput, request.data)
    try:
        with transaction.atomic():
            barber = locked_barber(data["barber"])
            if not manages_barber(request.user, barber):
                raise PermissionDenied()
            day = data["date"]
            start, end = data["start_time"], data["end_time"]
            hours = hours_for(day)
            if not hours or not (hours.open_time <= start < end <= hours.close_time) or not future(datetime.combine(day, start)):
                raise ValidationError("Block must be a future interval within opening hours")
            if conflicting(barber, day, start, end):
                return Response({"error": "Interval overlaps a booking or block"}, status=409)
            block = BarberBlock.objects.create(barber=barber, date=day, start_time=start, end_time=end, reason=data.get("reason", ""))
        return Response({"message": "time blocked", "block_id": block.pk}, status=201)
    except OperationalError:
        return busy()

@api_view(["DELETE"])
def delete_block(request, block_id):
    try:
        with transaction.atomic():
            block = get_object_or_404(BarberBlock.objects.select_related("barber"), pk=block_id)
            if not manages_barber(request.user, block.barber):
                raise PermissionDenied()
            locked_barber(block.barber_id)
            block.delete()
        return Response(status=204)
    except OperationalError:
        return busy()

@api_view(["GET"])
def calendar_view(request):
    data = parse(DayInput, request.query_params)
    barber = get_object_or_404(Barber, pk=data["barber"])
    if not manages_barber(request.user, barber):
        raise PermissionDenied()
    day = data["date"]
    hours = hours_for(day)
    if not hours:
        return Response([])
    bookings, blocks = intervals(barber, day)
    bookings = list(bookings.select_related("service"))
    blocks = list(blocks)
    _, close = bounds(day, hours)
    result = []
    for start in starts(day, hours):
        end = min(start + STEP, close)
        row = {"time": start.strftime("%H:%M"), "status": "available"}
        booking = next((b for b in bookings if overlaps(start.time(), end.time(), b.start_time, b.end_time)), None)
        block = next((b for b in blocks if overlaps(start.time(), end.time(), b.start_time, b.end_time)), None)
        if booking:
            row.update(status="booked", booking_id=booking.pk, customer=booking.customer_name,
                       phone=booking.customer_phone, service=booking.service.name,
                       duration=int((datetime.combine(day, booking.end_time)-datetime.combine(day, booking.start_time)).total_seconds()/60))
        elif block:
            row.update(status="blocked", reason=block.reason)
        result.append(row)
    return Response(result)

@api_view(["GET"])
def my_bookings(request):
    # Do not treat knowledge of a phone number as proof of ownership.
    rows = Booking.objects.filter(customer=request.user).select_related("barber", "service").order_by("-date", "-start_time")
    return Response([{"id": b.pk, "barber": b.barber.name, "service": b.service.name,
                      "date": b.date, "start_time": b.start_time, "end_time": b.end_time, "status": b.status} for b in rows])

@api_view(["GET"])
def barber_bookings(request):
    q = serializers.IntegerField(min_value=1)
    barber = get_object_or_404(Barber, pk=q.run_validation(request.query_params.get("barber")))
    if not manages_barber(request.user, barber):
        raise PermissionDenied()
    rows = Booking.objects.filter(barber=barber, status="booked").select_related("service").order_by("date", "start_time")
    return Response([{"id": b.pk, "customer": b.customer_name, "phone": b.customer_phone,
                      "service": b.service.name, "date": b.date, "start_time": b.start_time, "end_time": b.end_time} for b in rows])
