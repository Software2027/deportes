"""
Vistas de renderizado de plantillas para el Portal Ciudadano y App Ciclista.
"""

from datetime import date
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CircuitoGeneral, SubCircuito, Noticia, ComercioAdherido, RecorridoCiclista, Ciclista
from .utils import calcular_distancia_total_puntos


def index(request):
    """
    Landing pública del circuito ciclista municipal.
    Muestra el Hero, el circuito activo en modo lectura, noticias y formulario de contacto.
    """
    circuito_activo = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).first()

    noticias = Noticia.objects.filter(
        Q(estado='Publicado') | Q(estado__isnull=True) | Q(estado='')
    ).order_by('-fecha_publicacion')[:6]

    # Estadísticas aproximadas para el Hero
    total_comercios = circuito_activo.comercios.count() if circuito_activo else 0
    total_subcircuitos = circuito_activo.subcircuitos.count() if circuito_activo else 0

    context = {
        'circuito': circuito_activo,
        'noticias': noticias,
        'total_comercios': total_comercios,
        'total_subcircuitos': total_subcircuitos,
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
    if request.user.is_authenticated and not request.user.is_staff:
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

        # Iniciar sesión oficial de Django
        login(request, user)
        return redirect('mi_progreso')

    return render(request, 'ciudadano/login.html')


def logout_view(request):
    """Cierre de sesión del ciclista."""
    logout(request)
    return redirect('index')


def mapa_carrera_view(request):
    """
    Pantalla fullscreen de carrera con GPS activo y telemetría en tiempo real.
    Provee el circuito oficial de Malagueño, trazados de etapas, comercios y sesión de carrera.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user

    # Obtener el perfil del ciclista asociado al usuario autenticado
    ciclista = getattr(user, 'perfil_ciclista', None)
    if not ciclista:
        ciclista = Ciclista.objects.filter(
            Q(user=user) | Q(dni=user.username) | Q(email__iexact=user.email)
        ).first()

    circuito_activo = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).first()

    recorrido_actual = None
    if circuito_activo:
        recorrido_actual = RecorridoCiclista.objects.filter(
            ciclista=user,
            circuito=circuito_activo,
            estado__in=['EN_CURSO', 'PAUSADO']
        ).order_by('-inicio').first()

    punto_largada = None
    punto_meta = None
    radio_largada = 80
    if circuito_activo:
        punto_largada = circuito_activo.punto_largada
        punto_meta = circuito_activo.punto_meta
        radio_largada = circuito_activo.radio_largada_metros or 80

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
            dist_sub_m = calcular_distancia_total_puntos(puntos)
            distancia_total_m += dist_sub_m
            dist_sub_km = round(dist_sub_m / 1000.0, 1) if dist_sub_m > 0 else round(3.5 + idx * 1.5, 1)

            sub_dict = {
                'id': sub.id,
                'nombre': sub.nombre,
                'orden': sub.orden,
                'color': sub.color_capa,
                'puntos_count': len(coords),
                'distancia_km': dist_sub_km,
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

    distancia_total_km = round(distancia_total_m / 1000.0, 1) if distancia_total_m > 0 else 16.5

    context = {
        'ciclista': ciclista,
        'circuito': circuito_activo,
        'recorrido': recorrido_actual,
        'recorrido_id': recorrido_actual.id if recorrido_actual else 0,
        'estado_carrera': recorrido_actual.estado if recorrido_actual else 'LISTO',
        'modalidad_recorrido': recorrido_actual.modalidad if recorrido_actual else ('OFICIAL' if (circuito_activo and circuito_activo.fecha_evento and circuito_activo.fecha_evento == date.today()) else 'LIBRE'),
        'punto_largada': punto_largada,
        'punto_largada_json': list(punto_largada) if punto_largada else None,
        'punto_meta': punto_meta,
        'punto_meta_json': list(punto_meta) if punto_meta else None,
        'radio_largada_metros': radio_largada,
        'subcircuitos': subcircuitos_data,
        'subcircuito_actual': subcircuitos_data[0] if subcircuitos_data else None,
        'total_subcircuitos': len(subcircuitos_data),
        'distancia_total_km': distancia_total_km,
        'trazado_json': trazado_geojson,
        'comercios_json': comercios_geojson,
    }
    return render(request, 'ciudadano/mapa_carrera.html', context)


def mi_progreso_view(request):
    """
    Mini panel del ciclista (Dashboard post-login).
    Muestra el perfil oficial, circuito activo, estado de inscripción, KPIs reales de avance,
    subcircuitos validados, cronograma de paradas oficiales y mini mapa de la ruta.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user

    # Obtener el perfil del ciclista asociado al usuario autenticado
    ciclista = getattr(user, 'perfil_ciclista', None)
    if not ciclista:
        ciclista = Ciclista.objects.filter(
            Q(user=user) | Q(dni=user.username) | Q(email__iexact=user.email)
        ).first()

    circuito_activo = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).first()

    # Procesar Inscripción rápida al Circuito Activo
    if request.method == 'POST' and request.POST.get('accion') == 'inscribir':
        if circuito_activo:
            modalidad_inicial = 'OFICIAL' if (circuito_activo.fecha_evento and circuito_activo.fecha_evento == date.today()) else 'LIBRE'
            recorrido, created = RecorridoCiclista.objects.get_or_create(
                ciclista=user,
                circuito=circuito_activo,
                defaults={
                    'estado': 'EN_CURSO',
                    'modalidad': modalidad_inicial
                }
            )
            messages.success(
                request,
                f"¡Inscripción confirmada! Te has registrado en el '{circuito_activo.nombre}'. Tu dorsal es #{recorrido.id:04d}."
            )
        return redirect('mi_progreso')

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

            if not esta_inscripto or distancia_acumulada_km == 0:
                estado_sub = 'en-curso' if (idx == 0 and esta_inscripto) else 'pendiente'
                pct = 0
                validados_texto = f"0 de {checkpoints_sub or len(pts)} puntos"
            elif distancia_acumulada_km >= km_fin_etapa:
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
        subcircuitos_list = [
            {
                'nombre': 'Etapa Casco Histórico',
                'estado': 'en-curso' if esta_inscripto else 'pendiente',
                'estado_display': 'En curso' if esta_inscripto else 'Pendiente',
                'porcentaje': 25 if esta_inscripto else 0,
                'distancia': '4.5 km',
                'checkpoints': 3,
                'validados_texto': '0 de 3 puntos validados',
            }
        ]

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
    modalidad_display = 'Evento Oficial' if (recorrido_actual and recorrido_actual.modalidad == 'OFICIAL') else 'Libre / Práctica'

    context = {
        'ciclista': ciclista,
        'circuito': circuito_activo,
        'recorrido': recorrido_actual,
        'esta_inscripto': esta_inscripto,
        'esta_en_carrera': esta_en_carrera,
        'modalidad_display': modalidad_display,
        'porcentaje_total': porcentaje_total,
        'distancia_km': distancia_acumulada_km,
        'total_km': total_km_circuito,
        'tiempo_str': tiempo_str,
        'ritmo_str': ritmo_str,
        'checkpoints_validados': checkpoints_validados,
        'total_comercios': total_comercios_circuito,
        'nivel_ciclista': ciclista.nivel if (ciclista and ciclista.nivel) else 'Aficionado',
        'subcircuitos': subcircuitos_list,
        'cronograma': cronograma,
        'trazado_json': trazado_geojson,
        'comercios_json': comercios_geojson,
    }
    return render(request, 'ciudadano/mi_progreso.html', context)
