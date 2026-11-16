"""
Rutas públicas, experiencia del ciclista y endpoints de API de la aplicación Ciudadano.
"""
from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # -------------------------------------------------------------------------
    # Portal Público y Ciudadano
    # -------------------------------------------------------------------------
    path('', views.index, name='index'),
    path('noticias/', views.noticias_ciudadano_list, name='noticias_listado'),
    path('noticia/<int:pk>/', views.noticia_detalle, name='noticia_detalle'),
    path('comercios/', views.comercios_ciudadano_list, name='comercios_listado'),
    path('comercio/<int:pk>/', views.comercio_detalle, name='comercio_detalle'),
    path('circuitos/', views.circuitos_ciudadano_list, name='circuitos_listado'),
    path('circuitos/<int:circuito_id>/inscribirse/', views.inscribir_circuito_view, name='inscribir_circuito'),
    path('circuitos/inscribirse/', views.inscribir_circuito_view, name='inscribir_circuito_post'),
    path('contacto/', views.contacto_view, name='contacto'),
    path('contacto/enviar/', views.contacto_submit, name='contacto_submit'),
    path('inscripcion/', views.contacto_view, name='inscripcion'),

    # -------------------------------------------------------------------------
    # Experiencia Privada del Ciclista
    # -------------------------------------------------------------------------
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('mapa-carrera/', views.mapa_carrera_view, name='mapa_carrera'),
    path('mi-progreso/', views.mi_progreso_view, name='mi_progreso'),
    path('mis-circuitos/', views.circuitos_ciclista_view, name='circuitos_ciclista'),

    # -------------------------------------------------------------------------
    # Endpoints de API REST (Telemetría, Circuitos y Monitoreo)
    # -------------------------------------------------------------------------
    path('api/circuitos/activo/', api_views.CircuitoActivoAPIView.as_view(), name='api_circuito_activo'),
    path('api/recorrido/iniciar/', api_views.IniciarRecorridoAPIView.as_view(), name='api_recorrido_iniciar'),
    path('api/recorrido/detener/', api_views.RegistrarParadaAPIView.as_view(), name='api_recorrido_detener'),
    path('api/recorrido/pausar/', api_views.PausarRecorridoAPIView.as_view(), name='api_recorrido_pausar'),
    path('api/recorrido/finalizar/', api_views.FinalizarRecorridoAPIView.as_view(), name='api_recorrido_finalizar'),
    path('api/gps/batch/', api_views.BatchGPSAPIView.as_view(), name='api_gps_batch'),
    path('api/panel/monitoreo-vivo/', api_views.MonitoreoVivoAPIView.as_view(), name='api_monitoreo_vivo'),
    path('api/noticias/', api_views.NoticiaListAPIView.as_view(), name='api_noticias_list'),
]
