from rest_framework.permissions import BasePermission, SAFE_METHODS

def is_manager(user):
    return bool(user.is_authenticated and (user.is_superuser or user.is_staff))

def manages_barber(user, barber):
    return is_manager(user) or (
        user.is_authenticated and user.role == "barber" and barber.user_id == user.pk
    )

class PublicReadManagerWrite(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_manager(request.user)
