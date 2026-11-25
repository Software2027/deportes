"""
Middlewares institucionales del Sistema de Ciclismo y Movilidad de Malagueño.
1. RoleIsolationMiddleware: Aislamiento estricto de sesiones entre Administradores y Participantes/Ciclistas.
2. CustomErrorPagesMiddleware: Intercepta errores HTTP (404, 500, excepciones no controladas)
   para mostrar las plantillas institucionales oficiales de la Municipalidad de Malagueño.
"""
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout

logger = logging.getLogger(__name__)


class RoleIsolationMiddleware:
    """
    Garantiza el aislamiento total de sesiones y accesos entre el Panel Administrativo
    y el Portal del Participante (Ciclista):
    
    1. Si un usuario con sesión de ciclista/participante intenta entrar a una URL del panel (/panel/...),
       se le rechaza el acceso y se le redirige al login administrativo o a su portal correspondiente.
    2. Si un usuario con sesión administrativa (staff/superuser) intenta ingresar a áreas privadas
       del participante (/mi-progreso/, /mis-circuitos/, /mapa-carrera/), no se confunden los roles:
       se le informa que dichas áreas son exclusivas para participantes acreditados y se le redirige
       a su panel administrativo.
    3. Impide que un usuario acceda a ambos portales mezclando datos de sesión simultáneos en el mismo contexto.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        user = getattr(request, 'user', None)

        if user and user.is_authenticated:
            es_personal_admin = user.is_staff or user.is_superuser
            tipo_sesion = request.session.get('tipo_sesion')

            # Rutas exclusivas del Panel Administrativo
            if path.startswith('/panel/'):
                # Si está en el login del panel, permitir que login_admin_view gestione
                if path != '/panel/login/' and path != '/panel/logout/':
                    # Si no es staff ni superuser, o si su sesión fue marcada como 'ciclista'
                    if not es_personal_admin or tipo_sesion == 'ciclista':
                        try:
                            messages.error(
                                request,
                                "Acceso restringido: Esta sección requiere una sesión con privilegios administrativos del municipio."
                            )
                        except Exception:
                            pass
                        return redirect('panel_login')

            # Rutas privadas exclusivas del Participante Acreditado
            rutas_privadas_ciclista = ('/mi-progreso/', '/mis-circuitos/', '/mapa-carrera/', '/inscribir-circuito/')
            if any(path.startswith(r) for r in rutas_privadas_ciclista):
                # Si el usuario es administrador (staff/superuser) pero NO tiene un perfil de ciclista acreditado
                # o su sesión fue explícitamente iniciada como 'administrador'
                if es_personal_admin and tipo_sesion == 'administrador':
                    try:
                        messages.info(
                            request,
                            "Has ingresado con tu cuenta administrativa del municipio. "
                            "El área de progreso y GPS es de uso exclusivo para participantes acreditados. "
                            "Puedes gestionar los circuitos y ciclistas desde tu Panel de Control."
                        )
                    except Exception:
                        pass
                    return redirect('panel_dashboard')

        return self.get_response(request)


class CustomErrorPagesMiddleware:
    """
    Middleware para interceptar errores HTTP y excepciones no capturadas, mostrando
    las plantillas institucionales oficiales (errores/500.html, errores/404.html, etc.).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception as exc:
            return self.process_exception(request, exc)

        # Si una ruta pública no existe (404), mostrar el template oficial 404
        if response.status_code == 404 and not request.path.startswith('/admin/'):
            return self._render_error(request, '404', 404)

        # Si ocurre un error de servidor (500), mostrar el template oficial 500
        if response.status_code == 500 and not request.path.startswith('/admin/'):
            return self._render_error(request, '500', 500)

        return response

    def process_exception(self, request, exception):
        """
        Captura cualquier excepción no manejada durante la ejecución de vistas o middlewares
        y renderiza la plantilla institucional de error 500.
        """
        if request.path.startswith('/admin/'):
            return None

        logger.exception("Error 500 no controlado interceptado: %s", exception)
        return self._render_error(request, '500', 500, {'error_detalle': str(exception)})

    def _render_error(self, request, code, status_code, extra_context=None):
        ctx = extra_context or {}
        # Intentar cargar desde templates/errores/ primero, o fallback a templates/error/
        for folder in ('errores', 'error'):
            try:
                return render(request, f'{folder}/{code}.html', ctx, status=status_code)
            except Exception:
                continue
        return render(request, 'errores/500.html', ctx, status=status_code)
