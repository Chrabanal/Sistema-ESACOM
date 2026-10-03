from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import EsGerencia

from .models import Comuna, Promocion
from .serializers import ComunaSerializer, PromocionSerializer


class SoloLecturaSalvoGerenciaMixin:
    def get_permissions(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [EsGerencia()]
        return [IsAuthenticated()]


class ComunaViewSet(SoloLecturaSalvoGerenciaMixin, viewsets.ModelViewSet):
    queryset = Comuna.objects.all()
    serializer_class = ComunaSerializer
    filterset_fields = ["region"]


class PromocionViewSet(SoloLecturaSalvoGerenciaMixin, viewsets.ModelViewSet):
    queryset = Promocion.objects.all()
    serializer_class = PromocionSerializer
    filterset_fields = ["empresa", "activa"]
