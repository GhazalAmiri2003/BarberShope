from rest_framework import serializers
from .models import BusinessHours

class BusinessHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHours
        fields = "__all__"

    def validate(self, attrs):
        def value(key):
            return attrs.get(key, getattr(self.instance, key, None))
        if not value("is_closed") and value("open_time") >= value("close_time"):
            raise serializers.ValidationError("Opening time must precede closing time")
        qs = BusinessHours.objects.filter(day_of_week=value("day_of_week"))
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Business hours already exist for this day")
        return attrs
