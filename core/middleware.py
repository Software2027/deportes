"""
Middleware para interceptar errores HTTP y mostrar las plantillas institucionales
de la Municipalidad de Malagueño incluso en entorno de desarrollo con DEBUG=True.
"""
from django.shortcuts import render


"""
Middlewares institucionales del Sistema de Ciclismo y Movilidad de Malagueño.
1. CustomErrorPagesMiddleware: Muestra plantillas institucionales de error (404, etc.).
2. RoleIsolationMiddleware: Aislamiento estricto de sesiones entre Administradores y Participantes/Ciclistas.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout


class RoleIsolationMiddleware:
    """
    Garantiza el aislamiento total de sesiones y accesos entre el Panel Administrativo
    y el Portal del Participante (Ciclista):
    
    1. Si un usuario con sesión de ciclista/participante intenta entrar a una URL del panel (/panel/...),
       se le rechaza el acceso y se le redirige al login administrativo o a su portal correspondiente.
    2. Si un usuario con sesión administrativa (staff/superuser) intenta ingresar a áreas privadas
       del participante (/mi-progreso/, /mis-circuitos/, /mapa-carrera/), no se confunden los roles:
       se le informa que dichas áreas son exclusivas para participantes acreditados y se le ofrece
       ir a su panel administrativo o ingresar con su cuenta de participante.
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
                        messages.error(
                            request,
                            "Acceso restringido: Esta sección requiere una sesión con privilegios administrativos del municipio."
                        )
                        return redirect('panel_login')

            # Rutas privadas exclusivas del Participante Acreditado
            rutas_privadas_ciclista = ('/mi-progreso/', '/mis-circuitos/', '/mapa-carrera/')
            if any(path.startswith(r) for r in rutas_privadas_ciclista):
                # Si el usuario es administrador (staff/superuser) pero NO tiene un perfil de ciclista acreditado
                # o su sesión fue explícitamente iniciada como 'administrador'
                if es_personal_admin and tipo_sesion == 'administrador':
                    messages.info(
                        request,
                        "Has ingresado con tu cuenta administrativa del municipio. "
                        "El área de progreso y GPS es de uso exclusivo para participantes acreditados. "
                        "Puedes gestionar las carreras y ciclistas desde tu Panel de Control."
                    )
                    return redirect('panel_dashboard')

        return self.get_response(request)


class CustomErrorPagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Si una ruta pública no existe (404), mostrar el template oficial 404
        if response.status_code == 404 and not request.path.startswith('/admin/'):
            return render(request, 'errores/404.html', status=404)

        return response
