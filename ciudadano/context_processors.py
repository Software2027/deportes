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
