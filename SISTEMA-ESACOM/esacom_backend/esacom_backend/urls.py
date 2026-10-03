"""
URL configuration for esacom_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
from django.http import JsonResponse
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from catalogos.views import ComunaViewSet, PromocionViewSet
from integraciones.views import CargaExcelViewSet, ClaroImportViewSet, KPIRegistroViewSet, MetaKPICalidadViewSet, cargar_excel_view, sincronizar_google_sheets_view
from usuarios.views import AuditoriaUsuarioViewSet, EjecutivoViewSet, LogoutView, RutTokenObtainPairView, UsuarioSoporteViewSet, PermisosUsuarioViewSet
from core.views import estado_sistema
from ventas.views import (
    ApelacionViewSet,
    CorteViewSet,
    GestionViewSet,
    VentaViewSet,
    dashboard_accionables,
    dashboard_historico,
    dashboard_gerencia,
    dashboard_gerencia_buscar_usuario,
    dashboard_gerencia_usuario_detalle,
    dashboard_gerencia_cierres,
    dashboard_gerencia_cierre_detalle,
    dashboard_gerencia_cierre_csv,
    dashboard_kpi,
    dashboard_kpi_ejecutivos,
    resumen_equipo_view,
)

router = DefaultRouter()
router.register("ejecutivos", EjecutivoViewSet, basename="ejecutivo")
router.register("soporte/usuarios", UsuarioSoporteViewSet, basename="soporte-usuario")
router.register("soporte/auditoria", AuditoriaUsuarioViewSet, basename="soporte-auditoria")
router.register("permisos/usuarios", PermisosUsuarioViewSet, basename="permisos-usuario")
router.register("comunas", ComunaViewSet, basename="comuna")
router.register("promociones", PromocionViewSet, basename="promocion")
router.register("ventas", VentaViewSet, basename="venta")
router.register("cortes", CorteViewSet, basename="corte")
router.register("apelaciones", ApelacionViewSet, basename="apelacion")
router.register("gestiones", GestionViewSet, basename="gestion")
router.register("claro-import", ClaroImportViewSet, basename="claroimport")
router.register("cargas-excel", CargaExcelViewSet, basename="cargaexcel")
router.register("registros-kpi", KPIRegistroViewSet, basename="kpiregistro")
router.register("soporte/metas-kpi-calidad", MetaKPICalidadViewSet, basename="soporte-metas-kpi-calidad")

def health_view(request):
    return JsonResponse({'status': 'ok', 'service': 'esacom-backend'})


urlpatterns = [
    path('api/health/', health_view, name='health'),
    path('api/estado-sistema/', estado_sistema, name='estado-sistema'),
    path('admin/', admin.site.urls),
    # Login: POST {"rut": "...", "password": "..."} -> {"access": "...", "refresh": "..."}
    path('api/auth/login/', RutTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', LogoutView.as_view(), name='token_logout'),
    path('api/', include(router.urls)),
    path('api/dashboard/kpi/', dashboard_kpi, name='dashboard-kpi'),
    path('api/dashboard/kpi-ejecutivos/', dashboard_kpi_ejecutivos, name='dashboard-kpi-ejecutivos'),
    path('api/dashboard/accionables/', dashboard_accionables, name='dashboard-accionables'),
    path('api/dashboard/historico/', dashboard_historico, name='dashboard-historico'),
    path('api/dashboard/gerencia/', dashboard_gerencia, name='dashboard-gerencia'),
    path('api/dashboard/gerencia/usuarios/', dashboard_gerencia_buscar_usuario, name='dashboard-gerencia-usuarios'),
    path('api/dashboard/gerencia/usuarios/<int:pk>/', dashboard_gerencia_usuario_detalle, name='dashboard-gerencia-usuario-detalle'),
    path('api/dashboard/gerencia/cierres/', dashboard_gerencia_cierres, name='dashboard-gerencia-cierres'),
    path('api/dashboard/gerencia/cierres/<str:canal>/<str:camada>/', dashboard_gerencia_cierre_detalle, name='dashboard-gerencia-cierre-detalle'),
    path('api/dashboard/gerencia/cierres/<str:canal>/<str:camada>/csv/', dashboard_gerencia_cierre_csv, name='dashboard-gerencia-cierre-csv'),
    path('api/equipo/resumen/', resumen_equipo_view, name='equipo-resumen'),
    path('api/integraciones/cargar-excel/', cargar_excel_view, name='cargar-excel'),
    path('api/integraciones/sincronizar-google-sheets/', sincronizar_google_sheets_view, name='sincronizar-google-sheets'),
]
