"""
Enrutador principal del Sistema de Ciclismo Municipal.
Incluye rutas para el área ciudadana/pública y el panel de administración.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ciudadano.views import error_test_preview_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('panel/', include('panel.urls')),
    path('error/<str:code>/', error_test_preview_view, name='error_test_preview'),
    path('', include('ciudadano.urls')),
]

# Manejadores de errores personalizados oficiales de Django
handler400 = 'ciudadano.views.error_400_view'
handler403 = 'ciudadano.views.error_403_view'
handler404 = 'ciudadano.views.error_404_view'
handler500 = 'ciudadano.views.error_500_view'

# Servir archivos multimedia en entorno de desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
