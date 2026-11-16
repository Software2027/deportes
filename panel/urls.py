"""
Rutas del panel de gestión administrativa municipal.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_view, name='panel_dashboard'),
    path('dashboard/', views.dashboard_view, name='panel_dashboard_alias'),

    # Autenticación administrativa
    path('login/', views.login_admin_view, name='panel_login'),
    path('logout/', views.logout_admin_view, name='panel_logout'),

    # Módulo: Gestión de Ciclistas
    path('ciclistas/', views.ciclistas_list_view, name='panel_ciclistas_listado'),
    path('ciclistas/nuevo/', views.ciclista_create_view, name='panel_ciclistas_nuevo'),
    path('ciclistas/<int:pk>/', views.ciclista_detail_view, name='panel_ciclista_ver'),
    path('ciclistas/<int:pk>/editar/', views.ciclista_edit_view, name='panel_ciclista_editar'),
    path('ciclistas/<int:pk>/eliminar/', views.ciclista_delete_view, name='panel_ciclista_eliminar'),
    path('ciclistas/<int:pk>/estado/<str:nuevo_estado>/', views.ciclista_cambiar_estado_view, name='panel_ciclista_cambiar_estado'),
    path('ciclistas/exportar-csv/', views.ciclistas_exportar_csv_view, name='panel_ciclistas_exportar_csv'),

    # Módulo: Gestión de Comercios
    path('comercios/', views.comercios_list_view, name='panel_comercios_listado'),
    path('comercios/nuevo/', views.comercio_create_view, name='panel_comercio_nuevo'),
    path('comercios/<int:pk>/', views.comercio_detail_view, name='panel_comercio_ver'),
    path('comercios/<int:pk>/editar/', views.comercio_edit_view, name='panel_comercio_editar'),
    path('comercios/<int:pk>/eliminar/', views.comercio_delete_view, name='panel_comercio_eliminar'),

    # Módulo: Gestión de Circuitos y Trazador
    path('circuitos/', views.circuitos_list_view, name='panel_circuitos_listado'),
    path('circuitos/nuevo/', views.circuito_editor_view, name='panel_circuito_nuevo'),
    path('circuitos/<int:pk>/editar/', views.circuito_editor_view, name='panel_circuito_editar'),
    path('circuitos/<int:pk>/activar/', views.circuito_activar_view, name='panel_circuito_activar'),
    path('circuitos/<int:pk>/eliminar/', views.circuito_delete_view, name='panel_circuito_eliminar'),
    path('circuitos/api/guardar/', views.circuito_guardar_api_view, name='panel_circuito_guardar_api'),

    # Módulo: Ranking y Estadísticas de Eventos
    path('ranking/', views.ranking_evento_view, name='panel_ranking_evento'),
    path('ranking/<int:circuito_id>/', views.ranking_evento_view, name='panel_ranking_evento_circuito'),

    # Módulo: Gestión de Noticias
    path('noticias/', views.noticias_list_view, name='panel_noticias_listado'),
    path('noticias/nueva/', views.noticia_create_view, name='panel_noticia_nueva'),
    path('noticias/<int:pk>/editar/', views.noticia_edit_view, name='panel_noticia_editar'),
    path('noticias/<int:pk>/eliminar/', views.noticia_delete_view, name='panel_noticia_eliminar'),
    path('noticias/<int:pk>/estado/<str:nuevo_estado>/', views.noticia_cambiar_estado_view, name='panel_noticia_cambiar_estado'),
]

