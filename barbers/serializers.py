from rest_framework import serializers
from core.permissions import is_manager
from .models import Barber

class BarberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barber
        fields = ["id", "name", "services", "is_active", "user"]
        extra_kwargs = {"user": {"write_only": True}}

    def validate_user(self, user):
        if user.role != "barber":
            raise serializers.ValidationError("Choose a barber account")
        return user
