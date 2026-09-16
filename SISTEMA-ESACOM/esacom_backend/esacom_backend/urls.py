from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from usuarios.views import EjecutivoViewSet, LogoutView, RutTokenObtainPairView


router = DefaultRouter()
router.register("ejecutivos", EjecutivoViewSet, basename="ejecutivo")


def health_view(request):
    return JsonResponse({
        "status": "ok",
        "service": "esacom-backend",
    })


urlpatterns = [
    path("api/health/", health_view, name="health"),

    path("admin/", admin.site.urls),

    path(
        "api/auth/login/",
        RutTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),

    path(
        "api/auth/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    path(
        "api/auth/logout/",
        LogoutView.as_view(),
        name="token_logout",
    ),

    path("api/", include(router.urls)),
]