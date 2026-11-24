from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from core.permissions import PublicReadManagerWrite
from rest_framework.response import Response
from .models import Barber
from .serializers import BarberSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def barber_list(request):

    barbers = Barber.objects.filter(is_active=True)

    serializer = BarberSerializer(barbers, many=True)

    return Response(serializer.data)


from rest_framework import viewsets
from .models import Barber
from .serializers import BarberSerializer


class BarberViewSet(viewsets.ModelViewSet):

    queryset = Barber.objects.all()

    serializer_class = BarberSerializer
    permission_classes = [PublicReadManagerWrite]

    def get_queryset(self):
        from core.permissions import is_manager
        qs = super().get_queryset()
        return qs if is_manager(self.request.user) else qs.filter(is_active=True)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Deactivate this record instead of deleting it"}, status=405)
