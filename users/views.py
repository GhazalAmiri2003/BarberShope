from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, validate_phone

class AuthThrottle(SimpleRateThrottle):
    scope = "authentication"
    rate = "10/min"
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}

def tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}

@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            user = serializer.save()
    except IntegrityError:
        return Response({"error": "Unable to register this phone"}, status=400)
    return Response(tokens(user), status=201)

@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    phone = request.data.get("phone")
    password = request.data.get("password")
    if not isinstance(phone, str) or not isinstance(password, str) or len(password) > 128:
        return Response({"error": "invalid credentials"}, status=400)
    try:
        normalized = validate_phone(phone)
    except serializers.ValidationError:
        normalized = phone
    user = authenticate(request, phone=normalized, password=password)
    if user is None and normalized != phone:
        user = authenticate(request, phone=phone, password=password)
    if not user:
        return Response({"error": "invalid credentials"}, status=401)
    return Response(tokens(user))
