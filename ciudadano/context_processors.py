"""
Context Processors para el área ciudadana y ciclista.
Permite disponer de variables globales en los templates (ej: circuito activo actual).
"""

def circuito_activo_context(request):
    """
    Inyecta el circuito general activo en el contexto de todas las plantillas.
    Si la base de datos aún no ha sido migrada, maneja la excepción de forma segura.
    """
    try:
        from .models import CircuitoGeneral
        circuito_activo = CircuitoGeneral.objects.filter(activo=True).first()
    except Exception:
        circuito_activo = None

    return {
        'circuito_activo_global': circuito_activo
    }


def panel_global_context(request):
    """
    Inyecta métricas globales para el panel administrativo,
    incluyendo el número de ciclistas con solicitud en estado 'Pendiente'.
    """
    total_pendientes = 0
    # Se evalúa solo para rutas del panel administrativo o usuarios staff
    if request.path.startswith('/panel/') or (hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff):
        try:
            from .models import Ciclista
            total_pendientes = Ciclista.objects.filter(estado='Pendiente').count()
        except Exception:
            total_pendientes = 0

    return {
        'total_ciclistas_pendientes': total_pendientes
    }
