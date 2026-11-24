from rest_framework import serializers
from .models import Service

class ServiceSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(min_value=1, max_value=1439)
    class Meta:
        model = Service
        fields = "__all__"

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
