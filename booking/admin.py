from django.contrib import admin
from .models import Booking, BarberBlock

class ReadOnlyAdmin(admin.ModelAdmin):
    # Use the protected API for scheduling writes.
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Booking)
class BookingAdmin(ReadOnlyAdmin):
    list_display = ("customer_name", "barber", "service", "date", "start_time", "end_time", "status")
    list_filter = ("barber", "date", "status")

@admin.register(BarberBlock)
class BarberBlockAdmin(ReadOnlyAdmin):
    list_display = ("barber", "date", "start_time", "end_time", "reason")
