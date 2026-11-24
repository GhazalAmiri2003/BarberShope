from django.urls import path
from . import views

urlpatterns = [
    path("block-time/", views.block_time),
    path("available-slots/", views.available_slots),
    path("bookings/", views.create_booking),
    path("bookings/<int:booking_id>/cancel/", views.cancel_booking),
    path("calendar/", views.calendar_view),
    path("my-bookings/", views.my_bookings),
    path("barber-bookings/", views.barber_bookings),
    path("block/<int:block_id>/", views.delete_block),
]
