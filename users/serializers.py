from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from rest_framework import serializers
import phonenumbers

User = get_user_model()

def validate_phone(value):
    try:
        number = phonenumbers.parse(value, "IT")
    except phonenumbers.NumberParseException:
        raise serializers.ValidationError("Invalid phone number")
    if not phonenumbers.is_valid_number(number):
        raise serializers.ValidationError("Invalid phone number")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)

class RegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="first_name", max_length=100)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    class Meta:
        model = User
        fields = ["phone", "password", "name"]
        extra_kwargs = {"phone": {"validators": []}}

    def validate_phone(self, value):
        phone = validate_phone(value)
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Phone already registered")
        return phone

    def validate(self, attrs):
        try:
            password_validation.validate_password(attrs["password"], User(phone=attrs["phone"], first_name=attrs["first_name"]))
        except ValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data, role="customer")
