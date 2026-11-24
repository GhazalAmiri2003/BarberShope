from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from core.permissions import PublicReadManagerWrite
from rest_framework.response import Response
from .models import Service
from .serializers import ServiceSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def service_list(request):

    services = Service.objects.filter(is_active=True)

    serializer = ServiceSerializer(services, many=True)

    return Response(serializer.data)

from rest_framework import viewsets
from .models import Service
from .serializers import ServiceSerializer


class ServiceViewSet(viewsets.ModelViewSet):

    queryset = Service.objects.all()

    serializer_class = ServiceSerializer
    permission_classes = [PublicReadManagerWrite]

    def get_queryset(self):
        from core.permissions import is_manager
        qs = super().get_queryset()
        return qs if is_manager(self.request.user) else qs.filter(is_active=True)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Deactivate this record instead of deleting it"}, status=405)
