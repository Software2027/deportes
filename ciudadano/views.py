"""
Vistas de renderizado de plantillas para el Portal Ciudadano y App Ciclista.
"""

from datetime import date, datetime
import json
import re
from functools import wraps
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CircuitoGeneral, SubCircuito, Noticia, ComercioAdherido, RecorridoCiclista, Ciclista, TIPOS_MOVILIDAD
from .utils import calcular_distancia_total_puntos


def index(request):
    """
    Landing pública del circuito ciclista municipal.
    Muestra el Hero, circuitos activos, el mapa en modo lectura, noticias y formulario de contacto.
    """
    circuitos_activos_qs = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).order_by('nombre')

    circuitos_activos = list(circuitos_activos_qs)

    # Circuito seleccionado para visualización en mapa
    circuito_id_param = request.GET.get('circuito_id')
    circuito_activo = None
    if circuito_id_param:
        for c in circuitos_activos:
            if str(c.id) == str(circuito_id_param):
                circuito_activo = c
                break

    if not circuito_activo:
        circuito_activo = circuitos_activos[0] if circuitos_activos else None

    noticias = Noticia.objects.filter(
        Q(estado='Publicado') | Q(estado__isnull=True) | Q(estado='')
    ).order_by('-fecha_publicacion')[:6]

    # Estadísticas para el Hero y Cards de Métricas Reales
    total_comercios = circuito_activo.comercios.count() if circuito_activo else 0
    total_subcircuitos = circuito_activo.subcircuitos.count() if circuito_activo else 0

    stat_ciclistas = Ciclista.objects.filter(estado='Validado').count()
    if stat_ciclistas == 0:
        stat_ciclistas = Ciclista.objects.count()

    stat_km_rutas = round(sum(float(c.distancia_total_km or 0.0) for c in circuitos_activos), 1)
    stat_negocios = ComercioAdherido.objects.filter(
        Q(estado='Activo') | Q(estado__isnull=True) | Q(estado='')
    ).count()
    stat_circuitos = len(circuitos_activos)

    # Circuitos en los que el usuario ya está inscripto
    inscriptos_ids = set()
    if request.user.is_authenticated:
        inscriptos_ids = set(
            RecorridoCiclista.objects.filter(ciclista=request.user).values_list('circuito_id', flat=True)
        )

    context = {
        'circuito': circuito_activo,
        'circuitos_activos': circuitos_activos,
        'inscriptos_ids': inscriptos_ids,
        'noticias': noticias,
        'total_comercios': total_comercios,
        'total_subcircuitos': total_subcircuitos,
        'stat_ciclistas': stat_ciclistas,
        'stat_km_rutas': stat_km_rutas,
        'stat_negocios': stat_negocios,
        'stat_circuitos': stat_circuitos,
    }
    return render(request, 'ciudadano/index.html', context)


def noticias_ciudadano_list(request):
    """
    Portal público de noticias de la Municipalidad de Malagueño.
    Muestra todas las publicaciones oficiales con filtrado por categoría, búsqueda y paginador.
    """
    noticias_qs = Noticia.objects.filter(
        Q(estado='Publicado') | Q(estado__isnull=True) | Q(estado='')
    ).order_by('-fecha_publicacion')

    categoria_filtro = request.GET.get('categoria', '').strip()
    if categoria_filtro:
        noticias_qs = noticias_qs.filter(categoria=categoria_filtro)

    query_q = request.GET.get('q', '').strip()
    if query_q:
        noticias_qs = noticias_qs.filter(
            Q(titulo__icontains=query_q) |
            Q(contenido__icontains=query_q) |
            Q(autor_nombre__icontains=query_q)
        )

    categorias = [
        ('Urbanismo', 'Urbanismo'),
        ('Seguridad', 'Seguridad'),
        ('Comunidad', 'Comunidad'),
        ('Eventos', 'Eventos'),
        ('Oficial', 'Oficial'),
    ]

    total_noticias = noticias_qs.count()
    paginator = Paginator(noticias_qs, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'noticias': page_obj,
        'page_obj': page_obj,
        'total_noticias': total_noticias,
        'categoria_filtro': categoria_filtro,
        'query_q': query_q,
        'categorias': categorias,
    }
    return render(request, 'ciudadano/noticias_listado.html', context)


def noticia_detalle(request, pk):
    """
    Detalle completo de una noticia o comunicado del municipio.
    Incrementa el contador de lecturas y muestra noticias relacionadas.
    """
    noticia = get_object_or_404(Noticia, pk=pk)

    # Incrementar vistas para estadísticas
    try:
        noticia.vistas = (noticia.vistas or 0) + 1
        noticia.save(update_fields=['vistas'])
    except Exception:
        pass

    otras_noticias = Noticia.objects.exclude(pk=pk).filter(
        Q(estado='Publicado') | Q(estado__isnull=True) | Q(estado='')
    ).order_by('-fecha_publicacion')[:3]

    context = {
        'noticia': noticia,
        'otras_noticias': otras_noticias
    }
    return render(request, 'ciudadano/noticia_detalle.html', context)


def comercios_ciudadano_list(request):
    """
    Directorio público de comercios y puntos de asistencia adheridos al circuito.
    Ofrece filtrado por categoría, buscador general y mapa interactivo de Malagueño.
    """
    comercios_qs = ComercioAdherido.objects.filter(
        Q(estado='Activo') | Q(estado__isnull=True) | Q(estado='')
    ).order_by('nombre')

    categoria_filtro = request.GET.get('categoria', '').strip()
    if categoria_filtro:
        comercios_qs = comercios_qs.filter(categoria=categoria_filtro)

    query_q = request.GET.get('q', '').strip()
    if query_q:
        comercios_qs = comercios_qs.filter(
            Q(nombre__icontains=query_q) |
            Q(direccion__icontains=query_q) |
            Q(descripcion__icontains=query_q)
        )

    categorias = ComercioAdherido.CATEGORIAS

    total_comercios = comercios_qs.count()
    paginator = Paginator(comercios_qs, 9)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Serialización para el mapa de geolocalización
    comercios_mapa = []
    for c in comercios_qs:
        comercios_mapa.append({
            'id': c.id,
            'nombre': c.nombre,
            'categoria': c.get_categoria_display(),
            'lat': float(c.latitud),
            'lng': float(c.longitud),
            'direccion': c.direccion,
            'telefono': c.telefono,
            'url': f"/comercio/{c.id}/"
        })

    context = {
        'comercios': page_obj,
        'page_obj': page_obj,
        'total_comercios': total_comercios,
        'categoria_filtro': categoria_filtro,
        'query_q': query_q,
        'categorias': categorias,
        'comercios_mapa_json': json.dumps(comercios_mapa),
    }
    return render(request, 'ciudadano/comercios_listado.html', context)


def comercio_detalle(request, pk):
    """
    Ficha de detalle técnico y de servicios de un comercio o punto adherido.
    Incluye mapa con localización del local (Google Maps) e indicaciones de llegada.
    """
    comercio = get_object_or_404(ComercioAdherido, pk=pk)

    otros_comercios = ComercioAdherido.objects.exclude(pk=pk).filter(
        Q(estado='Activo') | Q(estado__isnull=True) | Q(estado='')
    ).order_by('?')[:3]

    google_maps_url = f"https://www.google.com/maps/search/?api=1&query={comercio.latitud},{comercio.longitud}"
    google_maps_embed = f"https://maps.google.com/maps?q={comercio.latitud},{comercio.longitud}&hl=es&z=16&output=embed"

    context = {
        'comercio': comercio,
        'otros_comercios': otros_comercios,
        'google_maps_url': google_maps_url,
        'google_maps_embed': google_maps_embed,
    }
    return render(request, 'ciudadano/comercio_detalle.html', context)


def contacto_view(request):
    """
    Vista de Inscripción Oficial de Ciclistas y Contacto Municipal.
    Permite a los ciclistas registrarse en los circuitos municipales,
    dejando su solicitud en estado 'Pendiente' para validación del administrador.
    """
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        dni = request.POST.get('dni', '').strip()
        email = request.POST.get('email', '').strip().lower()
        telefono = request.POST.get('telefono', '').strip()
        club_entidad = request.POST.get('club_entidad', '').strip() or 'Independiente'
        nivel = request.POST.get('nivel', 'Aficionado').strip()
        contacto_emergencia = request.POST.get('contacto_emergencia', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip() or None
        observaciones = request.POST.get('observaciones', '').strip()

        # Validaciones de campos obligatorios
        if not nombre or not dni or not email:
            messages.error(request, "Por favor completa todos los campos obligatorios: Nombre, DNI y Correo Electrónico.")
            return render(request, 'ciudadano/contacto.html', {'datos': request.POST})

        # Validación de Fecha de Nacimiento (límite entre 10 y 90 años)
        if fecha_nacimiento:
            try:
                fn_date = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
                hoy = date.today()
                edad = hoy.year - fn_date.year - ((hoy.month, hoy.day) < (fn_date.month, fn_date.day))
                if edad < 10 or edad > 90:
                    messages.error(
                        request,
                        f"La edad para inscribirse debe estar comprendida entre 10 y 90 años (edad calculada: {edad} años)."
                    )
                    return render(request, 'ciudadano/contacto.html', {'datos': request.POST})
            except (ValueError, TypeError):
                messages.error(request, "Por favor ingresa una fecha de nacimiento válida (AAAA-MM-DD).")
                return render(request, 'ciudadano/contacto.html', {'datos': request.POST})
        else:
            messages.error(request, "Por favor ingresa tu fecha de nacimiento.")
            return render(request, 'ciudadano/contacto.html', {'datos': request.POST})

        # Validación de Teléfono de Emergencia vs. Teléfono Personal
        tel_digitos = re.sub(r'\D', '', telefono)
        emerg_digitos = re.sub(r'\D', '', contacto_emergencia)
        if tel_digitos and emerg_digitos:
            # Si coinciden exactamente o uno es sufijo exacto del otro (ej. con o sin código de área)
            if tel_digitos == emerg_digitos or (len(tel_digitos) >= 7 and len(emerg_digitos) >= 7 and (tel_digitos.endswith(emerg_digitos) or emerg_digitos.endswith(tel_digitos))):
                messages.error(
                    request,
                    "El número de teléfono de contacto de emergencia debe ser distinto a tu número de teléfono personal."
                )
                return render(request, 'ciudadano/contacto.html', {'datos': request.POST})

        # Verificar duplicados por DNI (no repetidos en Ciclista ni en User)
        if Ciclista.objects.filter(dni__iexact=dni).exists() or User.objects.filter(username__iexact=dni).exists():
            messages.error(
                request,
                f"El DNI {dni} ya se encuentra registrado en el padrón de ciclistas. "
                f"Si ya te has inscripto, puedes verificar tu estado o iniciar sesión."
            )
            return render(request, 'ciudadano/contacto.html', {'datos': request.POST})

        # Verificar duplicados por Email (no repetidos en Ciclista ni en User)
        if Ciclista.objects.filter(email__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            messages.error(
                request,
                f"El correo electrónico '{email}' ya se encuentra registrado en el sistema. "
                f"Por favor utiliza otro correo o comunícate con la mesa de ayuda municipal."
            )
            return render(request, 'ciudadano/contacto.html', {'datos': request.POST})

        # Capturar foto carnet opcional
        foto = request.FILES.get('foto')

        # Crear nuevo Ciclista en estado Pendiente
        ciclista = Ciclista.objects.create(
            nombre=nombre,
            dni=dni,
            email=email,
            telefono=telefono,
            fecha_nacimiento=fecha_nacimiento,
            club_entidad=club_entidad,
            nivel=nivel,
            contacto_emergencia=contacto_emergencia,
            observaciones=observaciones,
            foto=foto,
            estado='Pendiente'
        )

        messages.success(
            request,
            f"¡Inscripción registrada con éxito para {ciclista.nombre}! Tu solicitud ha quedado en estado PENDIENTE "
            f"con identificador {ciclista.codigo_id}. La administración municipal revisará tu documentación y te notificará por correo."
        )
        return redirect(request.path or 'contacto')

    return render(request, 'ciudadano/contacto.html')


def contacto_submit(request):
    """
    Redirección de compatibilidad para inscripciones o consultas enviadas al endpoint alternativo.
    """
    return contacto_view(request)


# ==============================================================================
# Rutas de la App Ciclista (Fase 5 y Flujo de Acreditación Oficial)
# ==============================================================================

def login_view(request):
    """
    Vista de autenticación oficial para ciclistas acreditados.
    Permite iniciar sesión con DNI o Correo Electrónico (Gmail) y su Contraseña.
    Verifica que la solicitud del ciclista se encuentre en estado 'Validado'.
    """
    # Si ya está autenticado con sesión de ciclista, redirigir a mi progreso
    if request.user.is_authenticated and request.session.get('tipo_sesion') == 'ciclista':
        return redirect('mi_progreso')

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not identifier or not password:
            messages.error(request, "Por favor ingresa tu DNI o Correo Electrónico y tu Contraseña.")
            return render(request, 'ciudadano/login.html', {'initial_username': identifier})

        # Buscar usuario Django por username (DNI) o email (Gmail)
        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(username__iexact=identifier)
        ).first()

        if not user:
            # Si no existe usuario en auth_user, verificar si hay un Ciclista pendiente o rechazado
            ciclista_candidato = Ciclista.objects.filter(
                Q(email__iexact=identifier) | Q(dni__iexact=identifier)
            ).first()

            if ciclista_candidato:
                if ciclista_candidato.estado == 'Pendiente':
                    messages.warning(
                        request,
                        f"Hola {ciclista_candidato.nombre}. Tu solicitud ({ciclista_candidato.codigo_id}) "
                        f"aún está en estado PENDIENTE de revisión municipal. Te notificaremos cuando el administrador la apruebe."
                    )
                elif ciclista_candidato.estado == 'Rechazado':
                    messages.error(
                        request,
                        f"La solicitud ({ciclista_candidato.codigo_id}) de {ciclista_candidato.nombre} ha sido RECHAZADA. "
                        f"Comunícate con la Dirección de Deportes de Malagueño."
                    )
                else:
                    messages.error(request, "Las credenciales ingresadas son incorrectas.")
            else:
                messages.error(request, "No existe ninguna cuenta asociada a ese DNI o Correo Electrónico.")

            return render(request, 'ciudadano/login.html', {'initial_username': identifier})

        # Verificar contraseña
        if not user.check_password(password):
            messages.error(request, "Contraseña incorrecta. Por favor verifica tus credenciales.")
            return render(request, 'ciudadano/login.html', {'initial_username': identifier})

        # Verificar estado del Ciclista asociado
        ciclista = getattr(user, 'perfil_ciclista', None)
        if not ciclista:
            ciclista = Ciclista.objects.filter(
                Q(user=user) | Q(email__iexact=user.email) | Q(dni__iexact=user.username)
            ).first()

        if ciclista:
            if ciclista.estado == 'Pendiente':
                messages.warning(
                    request,
                    f"Hola {ciclista.nombre}. Tu solicitud ({ciclista.codigo_id}) aún se encuentra PENDIENTE de aprobación."
                )
                return render(request, 'ciudadano/login.html', {'initial_username': identifier})
            elif ciclista.estado == 'Rechazado':
                messages.error(
                    request,
                    f"Tu solicitud ({ciclista.codigo_id}) ha sido rechazada por la administración municipal."
                )
                return render(request, 'ciudadano/login.html', {'initial_username': identifier})
            elif ciclista.estado != 'Validado':
                messages.error(request, "Tu cuenta de ciclista no se encuentra habilitada para ingresar.")
                return render(request, 'ciudadano/login.html', {'initial_username': identifier})

        # Si el usuario es administrador/staff y no tiene perfil de ciclista acreditado,
        # indicarle que debe utilizar el portal interno de gestión
        if (user.is_staff or user.is_superuser) and not ciclista:
            messages.info(
                request,
                "Has ingresado credenciales correspondientes a un Administrador Municipal. "
                "Para acceder a la consola de gestión, por favor ingresa por el Acceso Interno."
            )
            return redirect('panel_login')

        if not ciclista:
            messages.error(request, "No se encontró un perfil de ciclista acreditado para este usuario.")
            return render(request, 'ciudadano/login.html', {'initial_username': identifier})

        # Iniciar sesión oficial de Django y etiquetar sesión de ciclista
        login(request, user)
        request.session['tipo_sesion'] = 'ciclista'
        request.session['ciclista_id'] = ciclista.id
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('mi_progreso')

    return render(request, 'ciudadano/login.html', {'next_url': request.GET.get('next', '')})


def logout_view(request):
    """Cierre de sesión del ciclista."""
    por_inactividad = request.GET.get('inactividad') == '1'
    logout(request)
    if por_inactividad:
        messages.info(request, "Tu sesión ha expirado tras 1 hora de inactividad por seguridad. Por favor ingresa nuevamente.")
        return redirect('login')
    return redirect('index')


def requiere_ciclista(view_func):
    """
    Decorador que asegura que el usuario esté autenticado con rol y sesión de ciclista/participante.
    Si un administrador municipal intenta ingresar a estas vistas, se le redirige al dashboard administrativo.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Si la sesión activa es de tipo administrador o si es staff/superuser sin sesión de ciclista
        if request.session.get('tipo_sesion') == 'administrador' or (
            (request.user.is_staff or request.user.is_superuser) and request.session.get('tipo_sesion') != 'ciclista'
        ):
            messages.info(
                request,
                "Has ingresado con tu cuenta administrativa del municipio. "
                "El área de progreso y GPS es de uso exclusivo para participantes acreditados. "
                "Puedes gestionar las carreras y ciclistas desde tu Panel de Control."
            )
            return redirect('panel_dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@requiere_ciclista
def mapa_carrera_view(request):
    """
    Pantalla fullscreen de carrera con GPS activo y telemetría en tiempo real.
    Provee el circuito oficial de Malagueño, trazados de etapas, comercios y sesión de carrera.
    """
    user = request.user

    # Obtener el perfil del ciclista asociado al usuario autenticado
    ciclista = getattr(user, 'perfil_ciclista', None)
    if not ciclista:
        ciclista = Ciclista.objects.filter(
            Q(user=user) | Q(dni=user.username) | Q(email__iexact=user.email)
        ).first()

    # Todos los circuitos activos en el sistema
    circuitos_activos_qs = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).order_by('nombre')
    circuitos_activos = list(circuitos_activos_qs)

    # Determinar qué circuito mostrar
    circuito_id_param = request.GET.get('circuito_id') or request.session.get('circuito_seleccionado_id')
    circuito_activo = None

    if circuito_id_param:
        for c in circuitos_activos:
            if str(c.id) == str(circuito_id_param):
                circuito_activo = c
                break

    if not circuito_activo:
        circuito_activo = circuitos_activos[0] if circuitos_activos else None

    if circuito_activo:
        request.session['circuito_seleccionado_id'] = circuito_activo.id

    # En modo libre interactivo permanente
    tipo_sesion = 'LIBRE_RECREATIVO'
    recorrido_actual = None
    if circuito_activo:
        recorrido_actual = RecorridoCiclista.objects.filter(
            ciclista=user,
            circuito=circuito_activo,
            estado__in=['LISTO', 'EN_CURSO', 'PAUSADO']
        ).order_by('-inicio').first()

    punto_largada = None
    punto_meta = None
    radio_largada = 20
    radio_meta = 20
    if circuito_activo:
        punto_largada = circuito_activo.punto_largada
        punto_meta = circuito_activo.punto_meta
        radio_largada = circuito_activo.radio_largada_metros or 20

    # Datos serializados para Leaflet y Etapas / Subcircuitos
    trazado_geojson = []
    subcircuitos_data = []
    comercios_geojson = []
    distancia_total_m = 0.0

    if circuito_activo:
        subs_list = list(circuito_activo.subcircuitos.all().order_by('orden'))
        for idx, sub in enumerate(subs_list):
            puntos = list(sub.trazado.values('latitud', 'longitud').order_by('orden'))
            coords = [[float(p['latitud']), float(p['longitud'])] for p in puntos]
            dist_sub_m = float(sub.distancia_metros)
            distancia_total_m += dist_sub_m
            dist_sub_km = float(sub.distancia_km)

            sub_dict = {
                'id': sub.id,
                'nombre': sub.nombre,
                'orden': sub.orden,
                'color': sub.color_capa,
                'puntos_count': len(coords),
                'distancia_km': dist_sub_km,
                'distancia_metros': dist_sub_m,
                'estado': 'en-curso' if idx == 0 else 'pendiente',
                'coordenadas': coords
            }
            trazado_geojson.append(sub_dict)
            subcircuitos_data.append(sub_dict)

        for com in circuito_activo.comercios.all():
            comercios_geojson.append({
                'id': com.id,
                'nombre': com.nombre,
                'categoria': com.get_categoria_display(),
                'categoria_codigo': com.categoria,
                'lat': float(com.latitud),
                'lng': float(com.longitud),
                'radio': com.radio_tolerancia_metros,
            })

    distancia_total_km = round(distancia_total_m / 1000.0, 2) if distancia_total_m > 0 else 0.0

    context = {
        'ciclista': ciclista,
        'circuito': circuito_activo,
        'circuitos_activos': circuitos_activos,
        'recorrido': recorrido_actual,
        'recorrido_id': recorrido_actual.id if recorrido_actual else 0,
        'estado_carrera': recorrido_actual.estado if recorrido_actual else 'LISTO',
        'tipo_sesion': tipo_sesion,
        'punto_largada': punto_largada,
        'punto_largada_json': list(punto_largada) if punto_largada else None,
        'punto_meta': punto_meta,
        'punto_meta_json': list(punto_meta) if punto_meta else None,
        'radio_largada_metros': radio_largada,
        'radio_meta_metros': radio_meta,
        'subcircuitos': subcircuitos_data,
        'subcircuito_actual': subcircuitos_data[0] if subcircuitos_data else None,
        'total_subcircuitos': len(subcircuitos_data),
        'distancia_total_km': distancia_total_km,
        'trazado_json': trazado_geojson,
        'comercios_json': comercios_geojson,
        'movilidades_permitidas': circuito_activo.movilidades_lista if circuito_activo else ['BICICLETA'],
        'tipos_movilidad_catalogo': TIPOS_MOVILIDAD,
    }
    return render(request, 'ciudadano/mapa_carrera.html', context)


@requiere_ciclista
def mi_progreso_view(request):
    """
    Mini panel del ciclista (Dashboard post-login).
    Muestra el perfil oficial, circuito activo, estado de inscripción, KPIs reales de avance,
    subcircuitos validados, cronograma de paradas oficiales y mini mapa de la ruta.
    """

    user = request.user

    # Obtener el perfil del ciclista asociado al usuario autenticado
    ciclista = getattr(user, 'perfil_ciclista', None)
    if not ciclista:
        ciclista = Ciclista.objects.filter(
            Q(user=user) | Q(dni=user.username) | Q(email__iexact=user.email)
        ).first()

    # Todos los circuitos activos en el sistema
    circuitos_activos = list(CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).order_by('nombre'))

    # Circuitos a los que el ciclista ya se encuentra inscripto
    recorridos_ciclista = RecorridoCiclista.objects.filter(
        ciclista=user,
        circuito__activo=True
    ).select_related('circuito').prefetch_related('circuito__subcircuitos', 'circuito__comercios').order_by('-inicio')

    recorrido_por_circuito = {}
    mis_circuitos_ids = []
    for r in recorridos_ciclista:
        if r.circuito_id not in recorrido_por_circuito:
            recorrido_por_circuito[r.circuito_id] = r
            mis_circuitos_ids.append(r.circuito_id)

    mis_circuitos_inscriptos = []
    for c_id in mis_circuitos_ids:
        r = recorrido_por_circuito[c_id]
        c = r.circuito
        dist_rec_km = float(getattr(r, 'distancia_km', 0.0) or 0.0)
        dist_tot_km = float(getattr(c, 'distancia_total_km', 1.0) or 1.0)
        pct = min(100, int((dist_rec_km / dist_tot_km) * 100)) if dist_tot_km > 0 else 0
        mis_circuitos_inscriptos.append({
            'circuito': c,
            'recorrido': r,
            'estado': r.estado,
            'distancia_km': dist_rec_km,
            'distancia_total_km': dist_tot_km,
            'porcentaje': pct,
            'es_actual': False,
        })

    # Procesar Adhesión / Habilitación de Circuito vía POST
    if request.method == 'POST' and request.POST.get('accion') == 'inscribir':
        c_id = request.POST.get('circuito_id')
        target_circuito = None
        if c_id:
            target_circuito = CircuitoGeneral.objects.filter(id=c_id, activo=True).first()

        if not target_circuito and circuitos_activos:
            target_circuito = circuitos_activos[0]

        if target_circuito:
            recorrido, created = RecorridoCiclista.objects.get_or_create(
                ciclista=user,
                circuito=target_circuito,
                defaults={
                    'estado': 'LISTO'
                }
            )
            if created:
                messages.success(
                    request,
                    f"¡Circuito sumado con éxito! Ahora tienes disponible '{target_circuito.nombre}' para pedalear o recorrer."
                )
            else:
                messages.info(
                    request,
                    f"Ya tienes registrado '{target_circuito.nombre}' en tu panel. Aquí puedes ver tu progreso."
                )
            return redirect(f"/mi-progreso/?circuito_id={target_circuito.id}")
        return redirect('mi_progreso')

    # Determinar qué circuito mostrar en Mi Progreso
    circuito_id_param = request.GET.get('circuito_id')
    circuito_activo = None

    if circuito_id_param:
        for c in circuitos_activos:
            if str(c.id) == str(circuito_id_param):
                circuito_activo = c
                break

    # Si no se pasó por parámetro, buscar entre los circuitos donde está inscripto
    if not circuito_activo and mis_circuitos_inscriptos:
        en_curso_item = next((it for it in mis_circuitos_inscriptos if it['estado'] in ['EN_CURSO', 'PAUSADO']), None)
        if en_curso_item:
            circuito_activo = en_curso_item['circuito']
        else:
            circuito_activo = mis_circuitos_inscriptos[0]['circuito']

    if not circuito_activo:
        circuito_activo = circuitos_activos[0] if circuitos_activos else None

    # Marcar cuál es el circuito actual en la lista de inscriptos y persistir selección en sesión
    if circuito_activo:
        request.session['circuito_seleccionado_id'] = circuito_activo.id
        for it in mis_circuitos_inscriptos:
            if it['circuito'].id == circuito_activo.id:
                it['es_actual'] = True

    # Recorrido del ciclista en el circuito activo
    recorrido_actual = None
    if circuito_activo:
        recorrido_actual = RecorridoCiclista.objects.filter(
            ciclista=user,
            circuito=circuito_activo
        ).order_by('-inicio').first()

    esta_inscripto = recorrido_actual is not None
    esta_en_carrera = esta_inscripto and recorrido_actual.estado in ['EN_CURSO', 'PAUSADO']

    # 1. Distancia Total Real del Circuito Activo
    distancia_total_circuito_m = 0.0
    if circuito_activo:
        for sub in circuito_activo.subcircuitos.all():
            pts = list(sub.trazado.values('latitud', 'longitud').order_by('orden'))
            distancia_total_circuito_m += calcular_distancia_total_puntos(pts)

    total_km_circuito = round(distancia_total_circuito_m / 1000.0, 1) if distancia_total_circuito_m > 0 else 16.5

    # 2. Telemetría y Distancia Real del Ciclista
    distancia_acumulada_km = 0.0
    tiempo_str = "0 min"
    ritmo_str = "0.0 km/h"

    if recorrido_actual:
        puntos_gps = list(recorrido_actual.puntos.values('latitud', 'longitud').order_by('timestamp'))
        if puntos_gps:
            dist_metros = calcular_distancia_total_puntos(puntos_gps)
            distancia_acumulada_km = round(dist_metros / 1000.0, 2)

        # Cálculo de tiempo transcurrido
        fin_tiempo = recorrido_actual.fin or timezone.now()
        delta_segundos = max(0, int((fin_tiempo - recorrido_actual.inicio).total_seconds()))
        horas = delta_segundos // 3600
        minutos = (delta_segundos % 3600) // 60

        if horas > 0:
            tiempo_str = f"{horas}h {minutos:02d}m"
        else:
            tiempo_str = f"{minutos} min"

        # Ritmo / Velocidad media
        if distancia_acumulada_km > 0 and delta_segundos > 30:
            horas_decimales = delta_segundos / 3600.0
            vel_media = round(distancia_acumulada_km / horas_decimales, 1)
            ritmo_str = f"{vel_media} km/h"
        else:
            ritmo_str = "0.0 km/h"

    # Porcentaje total completado
    porcentaje_total = 0
    if total_km_circuito > 0 and distancia_acumulada_km > 0:
        porcentaje_total = min(100, int(round((distancia_acumulada_km / total_km_circuito) * 100)))
    if recorrido_actual and recorrido_actual.estado == 'FINALIZADO':
        porcentaje_total = 100

    # 3. Checkpoints y Comercios Validados
    total_comercios_circuito = circuito_activo.comercios.count() if circuito_activo else 0
    comercios_visitados_ids = set()
    if recorrido_actual:
        comercios_visitados_ids = set(
            recorrido_actual.paradas_registradas.filter(es_comercio_adherido=True).values_list('comercio_id', flat=True)
        )
    checkpoints_validados = f"{len(comercios_visitados_ids)} / {total_comercios_circuito}"

    # 4. Desglose Real de Subcircuitos / Etapas
    subcircuitos_list = []
    if circuito_activo and circuito_activo.subcircuitos.exists():
        subs = list(circuito_activo.subcircuitos.all().order_by('orden'))
        km_recorridos_acum = 0.0

        for idx, sub in enumerate(subs):
            pts = list(sub.trazado.values('latitud', 'longitud').order_by('orden'))
            dist_sub_m = calcular_distancia_total_puntos(pts)
            dist_sub_km = round(dist_sub_m / 1000.0, 1) if dist_sub_m > 0 else round(3.5 + idx * 1.5, 1)
            checkpoints_sub = sub.comercios.count()

            km_inicio_etapa = km_recorridos_acum
            km_fin_etapa = km_recorridos_acum + dist_sub_km
            km_recorridos_acum = km_fin_etapa

            es_recorrido_finalizado = bool(recorrido_actual and recorrido_actual.estado == 'FINALIZADO')
            es_ultima_etapa = (idx == len(subs) - 1)
            casi_alcanzado = (es_ultima_etapa and distancia_acumulada_km >= (km_fin_etapa * 0.95))

            if not esta_inscripto or distancia_acumulada_km == 0:
                estado_sub = 'en-curso' if (idx == 0 and esta_inscripto) else 'pendiente'
                pct = 0
                validados_texto = f"0 de {checkpoints_sub or len(pts)} puntos"
            elif distancia_acumulada_km >= km_fin_etapa or es_recorrido_finalizado or casi_alcanzado:
                estado_sub = 'completado'
                pct = 100
                validados_texto = f"Etapa completada ({dist_sub_km} km)"
            elif distancia_acumulada_km > km_inicio_etapa:
                estado_sub = 'en-curso'
                avance = distancia_acumulada_km - km_inicio_etapa
                pct = min(99, max(5, int(round((avance / dist_sub_km) * 100))))
                validados_texto = f"{round(avance, 1)} de {dist_sub_km} km"
            else:
                estado_sub = 'pendiente'
                pct = 0
                validados_texto = f"0 de {checkpoints_sub or len(pts)} puntos"

            subcircuitos_list.append({
                'id': sub.id,
                'nombre': sub.nombre,
                'orden': sub.orden,
                'estado': estado_sub,
                'estado_display': 'Completado' if estado_sub == 'completado' else ('En curso' if estado_sub == 'en-curso' else 'Pendiente'),
                'porcentaje': pct,
                'distancia': f"{dist_sub_km} km",
                'checkpoints': checkpoints_sub or len(pts),
                'validados_texto': validados_texto,
                'color': sub.color_capa,
            })
    else:
        subcircuitos_list = []

    total_tramos = len(subcircuitos_list)

    # 5. Datos para Mini Mapa (Leaflet)
    trazado_geojson = []
    comercios_geojson = []
    if circuito_activo:
        for sub in circuito_activo.subcircuitos.all().order_by('orden'):
            puntos = list(sub.trazado.values('latitud', 'longitud').order_by('orden'))
            trazado_geojson.append({
                'nombre': sub.nombre,
                'color': sub.color_capa,
                'coordenadas': [[float(p['latitud']), float(p['longitud'])] for p in puntos]
            })
        for com in circuito_activo.comercios.all():
            comercios_geojson.append({
                'nombre': com.nombre,
                'categoria': com.get_categoria_display(),
                'lat': float(com.latitud),
                'lng': float(com.longitud),
            })

    # 6. Cronograma Real de Paradas del Circuito
    cronograma = []
    if circuito_activo:
        # Punto 1: Salida Oficial / Largada Km 0
        cronograma.append({
            'tipo': 'inicio',
            'titulo': 'Punto de Inicio: Km 0 (Línea de Largada)',
            'desc': f'Radio de largada oficial: {circuito_activo.radio_largada_metros or 80}m.',
            'hora': 'Salida Oficial',
            'estado': 'completed' if (recorrido_actual and recorrido_actual.estado in ['EN_CURSO', 'PAUSADO', 'FINALIZADO']) else 'current',
        })

        # Comercios y puntos adheridos
        for com in circuito_activo.comercios.all().order_by('id'):
            fue_visitado = com.id in comercios_visitados_ids
            cronograma.append({
                'tipo': 'comercio',
                'titulo': f"{com.nombre} ({com.get_categoria_display()})",
                'desc': com.descripcion or com.direccion or "Parada oficial del circuito municipal.",
                'hora': 'Validado' if fue_visitado else f'Radio: {com.radio_tolerancia_metros}m',
                'estado': 'completed' if fue_visitado else 'pending',
                'accion_url': '#mapa-circuito',
                'accion_texto': 'Ver en Mapa',
            })

        # Meta / Llegada
        cronograma.append({
            'tipo': 'meta',
            'titulo': f'Meta Oficial: {circuito_activo.nombre}',
            'desc': 'Llegada final del circuito y validación de marcas.',
            'hora': 'Meta',
            'estado': 'completed' if (recorrido_actual and recorrido_actual.estado == 'FINALIZADO') else 'pending',
        })

    # Modalidad
    modalidad_display = 'Libre Recreativo'

    # 7. Historial de Recorridos / Sesiones del Ciclista en este Circuito Específico
    historial_recorridos_data = []
    if circuito_activo:
        from .utils import calcular_distancia_metros
        historial_qs = RecorridoCiclista.objects.filter(
            ciclista=user,
            circuito=circuito_activo
        ).prefetch_related('puntos', 'paradas_registradas').order_by('-inicio')

        for rec in historial_qs:
            segundos_rec = 0
            duracion_formateada = "--:--:--"
            if rec.inicio and rec.fin:
                delta = (rec.fin - rec.inicio).total_seconds()
                if delta > 0:
                    segundos_rec = int(delta)
                    horas = segundos_rec // 3600
                    minutos = (segundos_rec % 3600) // 60
                    segs = segundos_rec % 60
                    duracion_formateada = f"{horas:02d}:{minutos:02d}:{segs:02d}"

            dist_km = float(rec.distancia_km or 0.0)
            vel_prom = 0.0
            if segundos_rec > 0 and dist_km > 0:
                vel_prom = round(dist_km / (segundos_rec / 3600.0), 1)

            # Velocidad máxima por deltas GPS
            vel_max = vel_prom
            puntos_rec = list(rec.puntos.order_by('timestamp').values('latitud', 'longitud', 'timestamp'))
            if len(puntos_rec) >= 2:
                max_v = 0.0
                for i in range(len(puntos_rec) - 1):
                    p_a, p_b = puntos_rec[i], puntos_rec[i + 1]
                    t_a, t_b = p_a['timestamp'], p_b['timestamp']
                    if t_a and t_b:
                        dt = (t_b - t_a).total_seconds()
                        if 1.0 <= dt <= 30.0:
                            d_m = calcular_distancia_metros(p_a['latitud'], p_a['longitud'], p_b['latitud'], p_b['longitud'])
                            v_kmh = (d_m / dt) * 3.6
                            if 0 < v_kmh < 95.0 and v_kmh > max_v:
                                max_v = v_kmh
                if max_v > 0:
                    vel_max = round(max(max_v, vel_prom), 1)
            elif vel_prom > 0:
                vel_max = round(vel_prom * 1.15, 1)

            paradas_count = rec.paradas_registradas.count()

            # Conversión explícita a la zona horaria oficial argentina (UTC-3)
            inicio_local = timezone.localtime(rec.inicio) if rec.inicio else None
            fecha_str = inicio_local.strftime("%d/%m/%Y %H:%M") if inicio_local else "--"

            # Evaluación de completitud del recorrido
            dist_total_circuito = float(circuito_activo.distancia_total_km or 0.0) if circuito_activo else 0.0
            es_completado = rec.es_completado if hasattr(rec, 'es_completado') else False
            if not es_completado and rec.estado == 'FINALIZADO':
                if dist_total_circuito > 0 and dist_km >= (dist_total_circuito * 0.85):
                    es_completado = True
                elif dist_total_circuito == 0 and dist_km > 0.5:
                    es_completado = True

            historial_recorridos_data.append({
                'id': rec.id,
                'inicio': rec.inicio,
                'inicio_local': inicio_local,
                'fecha_str': fecha_str,
                'tipo_movilidad': rec.tipo_movilidad or 'BICICLETA',
                'tipo_movilidad_display': rec.get_tipo_movilidad_display() if hasattr(rec, 'get_tipo_movilidad_display') else (rec.tipo_movilidad or 'Bicicleta'),
                'estado': rec.estado,
                'estado_display': rec.get_estado_display(),
                'finalizado': rec.estado == 'FINALIZADO',
                'completado': es_completado,
                'duracion_str': duracion_formateada,
                'distancia_km': dist_km,
                'vel_prom': vel_prom,
                'vel_max': vel_max,
                'paradas_count': paradas_count,
            })

    # Paginación para historial de recorridos (5 por página)
    paginator_historial = Paginator(historial_recorridos_data, 5)
    page_number_hist = request.GET.get('page')
    page_obj_historial = paginator_historial.get_page(page_number_hist)

    context = {
        'ciclista': ciclista,
        'circuito': circuito_activo,
        'circuitos_activos': circuitos_activos,
        'mis_circuitos_inscriptos': mis_circuitos_inscriptos,
        'inscriptos_ids': set(mis_circuitos_ids),
        'total_inscriptos': len(mis_circuitos_inscriptos),
        'tiene_inscriptos': len(mis_circuitos_inscriptos) > 0,
        'recorrido': recorrido_actual,
        'esta_inscripto': esta_inscripto,
        'esta_en_carrera': esta_en_carrera,
        'porcentaje_total': porcentaje_total,
        'distancia_km': distancia_acumulada_km,
        'total_km': total_km_circuito,
        'tiempo_str': tiempo_str,
        'ritmo_str': ritmo_str,
        'checkpoints_validados': checkpoints_validados,
        'total_comercios': total_comercios_circuito,
        'nivel_ciclista': ciclista.nivel if (ciclista and ciclista.nivel) else 'Aficionado',
        'subcircuitos': subcircuitos_list,
        'total_tramos': total_tramos,
        'cronograma': cronograma,
        'trazado_json': trazado_geojson,
        'comercios_json': comercios_geojson,
        'historial_recorridos': page_obj_historial,
        'page_obj_historial': page_obj_historial,
        'total_historial': len(historial_recorridos_data),
    }
    return render(request, 'ciudadano/mi_progreso.html', context)


@login_required(login_url='login')
def inscribir_circuito_view(request, circuito_id=None):
    """
    Agrega o habilita formalmente un circuito municipal al panel del ciclista.
    """
    c_id = circuito_id or request.POST.get('circuito_id') or request.GET.get('circuito_id')
    if not c_id:
        return redirect('mi_progreso')

    circuito = get_object_or_404(CircuitoGeneral, id=c_id, activo=True)

    recorrido_libre = RecorridoCiclista.objects.filter(
        ciclista=request.user,
        circuito=circuito
    ).first()

    if not recorrido_libre:
        recorrido_libre = RecorridoCiclista.objects.create(
            ciclista=request.user,
            circuito=circuito,
            estado='LISTO'
        )
        messages.success(
            request,
            f"¡Circuito sumado con éxito! Se ha añadido '{circuito.nombre}' a tu panel para que lo recorras cuando desees."
        )
    else:
        messages.info(
            request,
            f"El circuito '{circuito.nombre}' ya se encuentra en tu panel."
        )
    return redirect(f"/mi-progreso/?circuito_id={circuito.id}")


def circuitos_ciudadano_list(request):
    """
    Directorio público institucional de circuitos de Malagueño (/circuitos/).
    Utiliza exclusivamente la plantilla pública con base_ciudadano.html.
    """
    circuitos_activos = list(CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).order_by('nombre'))

    inscriptos_ids = set()
    if request.user.is_authenticated:
        inscriptos_ids = set(
            RecorridoCiclista.objects.filter(ciclista=request.user).values_list('circuito_id', flat=True)
        )

    circuito_activo = circuitos_activos[0] if circuitos_activos else None

    context = {
        'circuitos_activos': circuitos_activos,
        'inscriptos_ids': inscriptos_ids,
        'circuito': circuito_activo,
    }
    return render(request, 'ciudadano/circuitos_listado.html', context)


@requiere_ciclista
def circuitos_ciclista_view(request):
    """
    Catálogo de circuitos dentro de la experiencia privada del ciclista acreditado (/mis-circuitos/).
    Utiliza exclusivamente la plantilla del panel del ciclista con base_ciclista.html.
    """
    circuitos_activos = list(CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).order_by('nombre'))

    inscriptos_ids = set(
        RecorridoCiclista.objects.filter(ciclista=request.user).values_list('circuito_id', flat=True)
    )
    ciclista = Ciclista.objects.filter(user=request.user).first()
    circuito_activo = circuitos_activos[0] if circuitos_activos else None

    context = {
        'circuitos_activos': circuitos_activos,
        'inscriptos_ids': inscriptos_ids,
        'circuito': circuito_activo,
        'ciclista': ciclista,
    }
    return render(request, 'ciudadano/circuitos_ciclista.html', context)


# ==============================================================================
# MANEJADORES DE ERRORES HTTP PERSONALIZADOS (404, 500, 403, 400, 503)
# ==============================================================================

def error_404_view(request, exception=None):
    """Página de error 404 personalizada - Página no encontrada."""
    return render(request, 'errores/404.html', status=404)


def error_500_view(request):
    """Página de error 500 personalizada - Error interno del servidor."""
    return render(request, 'errores/500.html', status=500)


def error_403_view(request, exception=None):
    """Página de error 403 personalizada - Acceso denegado."""
    return render(request, 'errores/403.html', status=403)


def error_400_view(request, exception=None):
    """Página de error 400 personalizada - Solicitud incorrecta."""
    return render(request, 'errores/400.html', status=400)


def error_test_preview_view(request, code):
    """
    Vista auxiliar para previsualizar las páginas de error en entorno de desarrollo.
    Ejemplo: /error/404/, /error/500/, /error/403/, /error/400/, /error/503/
    """
    code_str = str(code)
    plantilla = f'errores/{code_str}.html'
    status_int = int(code_str) if code_str.isdigit() else 200
    try:
        return render(request, plantilla, status=status_int)
    except Exception:
        return render(request, 'errores/404.html', status=404)
