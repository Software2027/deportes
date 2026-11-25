"""
Vistas para el Panel de Gestión Administrativa Municipal.
Control de acceso interno, dashboard operativo y monitoreo en tiempo real.
"""

import os
import csv
import json
import re
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Max, Avg
from datetime import timedelta, date, datetime, time
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from ciudadano.models import (
    CircuitoGeneral, SubCircuito, CategoriaComercio, ComercioAdherido,
    RecorridoCiclista, Noticia, RegistroGPS, Ciclista, PuntosTramo, ParadaRecorrido,
    TIPOS_MOVILIDAD, DIFICULTADES_CIRCUITO
)
from ciudadano.utils import calcular_distancia_metros


def requiere_staff(view_func):
    """
    Decorador que asegura que el usuario esté autenticado, posea permisos
    de staff o superusuario y cuente con sesión de tipo administrativo
    para acceder a las vistas del panel de administración municipal.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Debe iniciar sesión para acceder al panel de administración.")
            return redirect('panel_login')
        if not (request.user.is_staff or request.user.is_superuser) or request.session.get('tipo_sesion') == 'ciclista':
            messages.error(request, "Acceso restringido: Se requieren permisos administrativos para acceder.")
            return redirect('panel_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _get_categorias_comercio():
    """
    Retorna la lista ordenada de categorías disponibles para comercios, combinando
    las categorías creadas por el superusuario en /admin con las opciones base.
    """
    cats_db = list(CategoriaComercio.objects.values_list('nombre', flat=True))
    default_cats = [c[0] for c in ComercioAdherido.CATEGORIAS]
    combinadas = []
    for c in cats_db + default_cats:
        c_clean = c.strip()
        if c_clean and c_clean not in combinadas:
            combinadas.append(c_clean)
    return sorted(combinadas)


def login_admin_view(request):
    """
    Vista de Inicio de Sesión Administrativo ('Acceso Interno').
    Autentica contra credenciales válidas con contraseñas hasheadas (PBKDF2/SHA256).
    Permite ingreso con correo electrónico o con nombre de usuario.
    Solo otorga acceso a usuarios con rol staff o superusuario.
    """
    # Si ya está autenticado con sesión administrativa activa, redirigir directo al dashboard
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser) and request.session.get('tipo_sesion') == 'administrador':
        return redirect('panel_dashboard')

    if request.method == 'POST':
        email_or_user = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not email_or_user or not password:
            messages.error(request, "Por favor complete su correo electrónico y contraseña.")
            return render(request, 'panel/login.html')

        # 1. Intentar autenticación por email (case-insensitive) o por username
        user_to_auth = None
        user_by_email = User.objects.filter(email__iexact=email_or_user).first()
        if user_by_email:
            user_to_auth = authenticate(request, username=user_by_email.username, password=password)

        if not user_to_auth:
            user_to_auth = authenticate(request, username=email_or_user, password=password)

        # 2. Validación estricta de credenciales
        if not user_to_auth:
            messages.error(request, "Credenciales incorrectas: Correo electrónico o contraseña inválidos.")
            return render(request, 'panel/login.html')

        if not user_to_auth.is_active:
            messages.error(request, "Esta cuenta se encuentra inactiva. Contacte al administrador central.")
            return render(request, 'panel/login.html')

        if not (user_to_auth.is_staff or user_to_auth.is_superuser):
            messages.error(request, "Acceso denegado: El usuario no cuenta con permisos administrativos para el panel.")
            return render(request, 'panel/login.html')

        # 3. Iniciar sesión y etiquetar sesión de administrador
        login(request, user_to_auth)
        request.session['tipo_sesion'] = 'administrador'
        messages.success(
            request,
            f"¡Bienvenido al Portal de Gestión, {user_to_auth.first_name or user_to_auth.username}!"
        )
        return redirect('panel_dashboard')

    return render(request, 'panel/login.html')


def _formatear_tiempo_relativo(dt):
    """Retorna una cadena legible en español del tiempo transcurrido desde una fecha."""
    if not dt:
        return "reciente"
    ahora = timezone.now()
    diff = ahora - dt
    segundos = int(diff.total_seconds())
    if segundos < 60:
        return "hace instantes"
    minutos = segundos // 60
    if minutos < 60:
        return f"hace {minutos}m"
    horas = minutos // 60
    if horas < 24:
        return f"hace {horas}h"
    dias = horas // 24
    if dias == 1:
        return "ayer"
    if dias < 7:
        return f"hace {dias}d"
    return dt.strftime("%d/%m")


def _generar_grafico_semanal_svg(dias_semana):
    """
    Genera los paths SVG (área y línea) con curvas de Bézier cúbicas suaves
    para representar con total precisión los datos reales de los últimos 7 días.
    Coordenadas: X de 50 a 880 (ancho útil 830, paso 830/6 ~ 138.33)
                 Y de 230 (0) a 30 (max_val) (alto útil 200)
    """
    max_val = max(
        max([d['inscritos'] for d in dias_semana]),
        max([d['activos'] for d in dias_semana]),
        4
    )

    # 5 niveles de líneas horizontales para el Eje Y
    eje_y = [
        {'y': 30, 'valor': max_val},
        {'y': 80, 'valor': int(round(max_val * 0.75))},
        {'y': 130, 'valor': int(round(max_val * 0.5))},
        {'y': 180, 'valor': int(round(max_val * 0.25))},
        {'y': 230, 'valor': 0},
    ]

    def _calcular_puntos(clave, clave_opuesta):
        pts = []
        for i, d in enumerate(dias_semana):
            x = 50.0 + i * (830.0 / 6.0)
            val = d[clave]
            val_op = d[clave_opuesta]
            y = 230.0 - (float(val) / float(max_val)) * 190.0
            pts.append({
                'x': round(x, 1),
                'y': round(y, 1),
                'val': val,
                'val_opuesto': val_op,
                'label': d['label'],
                'fecha_str': d.get('fecha_str', '')
            })
        return pts

    def _construir_bezier_path(pts):
        if not pts:
            return "", ""
        line_path = f"M {pts[0]['x']},{pts[0]['y']}"
        for i in range(len(pts) - 1):
            p0 = pts[i]
            p1 = pts[i + 1]
            cpx1 = round(p0['x'] + (p1['x'] - p0['x']) / 2.0, 1)
            cpy1 = p0['y']
            cpx2 = cpx1
            cpy2 = p1['y']
            line_path += f" C {cpx1},{cpy1} {cpx2},{cpy2} {p1['x']},{p1['y']}"

        area_path = f"{line_path} L {pts[-1]['x']},230 L {pts[0]['x']},230 Z"
        return line_path, area_path

    pts_inscritos = _calcular_puntos('inscritos', 'activos')
    pts_activos = _calcular_puntos('activos', 'inscritos')

    line_inscritos, area_inscritos = _construir_bezier_path(pts_inscritos)
    line_activos, area_activos = _construir_bezier_path(pts_activos)

    total_activos_semana = sum(d['activos'] for d in dias_semana)
    total_inscritos_semana = sum(d['inscritos'] for d in dias_semana)
    pico = max(dias_semana, key=lambda x: x['activos']) if dias_semana else None

    return {
        'eje_y': eje_y,
        'dias': [d['label'] for d in dias_semana],
        'line_inscritos': line_inscritos,
        'area_inscritos': area_inscritos,
        'line_activos': line_activos,
        'area_activos': area_activos,
        'ultimo_pto_inscritos': pts_inscritos[-1] if pts_inscritos else None,
        'ultimo_pto_activos': pts_activos[-1] if pts_activos else None,
        'pts_inscritos': pts_inscritos,
        'pts_activos': pts_activos,
        'total_activos_semana': total_activos_semana,
        'total_inscritos_semana': total_inscritos_semana,
        'pico_dia': pico['label'] if (pico and pico['activos'] > 0) else "Sin pico",
        'pico_val': pico['activos'] if pico else 0,
        'promedio_diario': round(total_activos_semana / 7.0, 1),
    }


@requiere_staff
def dashboard_view(request):
    """
    Dashboard principal del Panel de Administración Municipal.
    Presenta KPIs, métricas reales, eventos del sistema y gráficos calculados
    dinámicamente desde la base de datos de Malagueño.
    """

    # 1. Métricas Clave de Participantes / Ciclistas (Exclusivo de la tabla de Ciclistas)
    total_participantes = Ciclista.objects.count()
    ciclistas_aprobados = Ciclista.objects.filter(estado__in=['Validado', 'Aprobado']).count()
    ciclistas_pendientes = Ciclista.objects.filter(estado='Pendiente').count()
    ciclistas_rechazados = Ciclista.objects.filter(estado='Rechazado').count()

    # 2. Métricas de Circuitos y Rutas
    circuitos_activos = CircuitoGeneral.objects.filter(activo=True).count()
    total_circuitos = CircuitoGeneral.objects.count()
    circuito_activo = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
        'subcircuitos__trazado',
        'comercios'
    ).first()
    total_etapas = circuito_activo.subcircuitos.count() if circuito_activo else 0

    # 3. Métricas de Comercios Aliados
    total_comercios = ComercioAdherido.objects.count()
    comercios_activos = ComercioAdherido.objects.filter(estado='Activo').count()
    comercios_revision = ComercioAdherido.objects.filter(estado='En Revision').count()

    # 4. Cálculo de Kilómetros Reales Acumulados
    recorridos_todos = RecorridoCiclista.objects.select_related('circuito').all()
    total_recorridos = recorridos_todos.count()
    recorridos_en_curso = recorridos_todos.filter(estado='EN_CURSO').count()
    km_acumulados = 0.0

    for r in recorridos_todos:
        dist_real = float(r.distancia_km or 0.0)
        if dist_real > 0:
            km_acumulados += dist_real
        elif r.circuito and r.circuito.distancia_total_km:
            if r.estado == 'FINALIZADO':
                km_acumulados += float(r.circuito.distancia_total_km)

    if km_acumulados >= 1000:
        km_totales_str = f"{km_acumulados / 1000.0:.1f}k"
    elif km_acumulados > 0:
        km_totales_str = f"{km_acumulados:.1f} km"
    else:
        km_totales_str = "0.0 km"

    # 5. Participación Semanal Real (Últimos 7 días)
    dias_semana = []
    hoy = timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date()
    dias_nombres_es = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}

    for i in range(6, -1, -1):
        d = hoy - timedelta(days=i)
        nombre_dia = 'Hoy' if i == 0 else dias_nombres_es[d.weekday()]

        inicio_dia = timezone.make_aware(datetime.combine(d, time.min))
        fin_dia = timezone.make_aware(datetime.combine(d, time.max))

        cnt_inscritos = Ciclista.objects.filter(fecha_registro__range=(inicio_dia, fin_dia)).count()
        cnt_activos = RecorridoCiclista.objects.filter(inicio__range=(inicio_dia, fin_dia)).count()

        dias_semana.append({
            'fecha': d,
            'fecha_str': d.strftime("%d/%m"),
            'label': nombre_dia,
            'inscritos': cnt_inscritos,
            'activos': cnt_activos
        })

    grafico_semanal = _generar_grafico_semanal_svg(dias_semana)

    # 6. Actividad Reciente Real Unificada
    eventos = []

    # 6.1 Recorridos de Ciclistas
    for rec in RecorridoCiclista.objects.select_related('ciclista', 'circuito').order_by('-inicio')[:6]:
        nombre_u = rec.ciclista.get_full_name() or rec.ciclista.username
        nom_circuito = rec.circuito.nombre if rec.circuito else "Circuito Municipal"
        if rec.estado == 'FINALIZADO':
            accion = f"Completó {nom_circuito}"
            color = 'green'
            fecha_ev = rec.fin or rec.inicio
        elif rec.estado == 'EN_CURSO':
            accion = f"Inició recorrido en {nom_circuito}"
            color = 'green'
            fecha_ev = rec.inicio
        else:
            accion = f"Pausó marcha en {nom_circuito}"
            color = 'amber'
            fecha_ev = rec.inicio
        eventos.append({
            'usuario': nombre_u,
            'accion': accion,
            'timestamp': fecha_ev,
            'estado_color': color
        })

    # 6.2 Paradas Registradas en Comercios / Puntos de Control
    for par in ParadaRecorrido.objects.select_related('recorrido__ciclista', 'comercio').order_by('-timestamp')[:6]:
        nombre_u = par.recorrido.ciclista.get_full_name() or par.recorrido.ciclista.username
        nom_parada = par.nombre_parada or (par.comercio.nombre if par.comercio else 'Punto de Asistencia')
        eventos.append({
            'usuario': nombre_u,
            'accion': f"Parada en {nom_parada}",
            'timestamp': par.timestamp,
            'estado_color': 'blue'
        })

    # 6.3 Nuevas Inscripciones de Ciclistas
    for cic in Ciclista.objects.select_related('user').order_by('-fecha_registro')[:6]:
        nombre_u = cic.nombre or (cic.user.get_full_name() if cic.user else cic.email)
        if cic.estado in ['Validado', 'Aprobado']:
            accion = "Ciclista validado y acreditado"
            color = 'green'
        elif cic.estado == 'Pendiente':
            accion = "Solicitud de inscripción recibida"
            color = 'amber'
        else:
            accion = "Solicitud rechazada"
            color = 'blue'
        eventos.append({
            'usuario': nombre_u,
            'accion': accion,
            'timestamp': cic.fecha_registro,
            'estado_color': color
        })

    # 6.4 Noticias y Comunicados
    for noti in Noticia.objects.order_by('-fecha_publicacion')[:3]:
        eventos.append({
            'usuario': 'Prensa Municipal',
            'accion': f"Noticia: {noti.titulo[:36]}...",
            'timestamp': noti.fecha_publicacion,
            'estado_color': 'green'
        })

    # Ordenar unificados por fecha descendente
    eventos.sort(key=lambda x: x['timestamp'] if x['timestamp'] else timezone.now(), reverse=True)
    actividad_reciente = []
    for ev in eventos[:5]:
        actividad_reciente.append({
            'usuario': ev['usuario'],
            'accion': ev['accion'],
            'tiempo': _formatear_tiempo_relativo(ev['timestamp']),
            'estado_color': ev['estado_color']
        })

    # 7. Impacto Comercial Local Real
    impacto_comercial = []
    paradas_comercios = ParadaRecorrido.objects.filter(
        es_comercio_adherido=True, comercio__isnull=False
    ).values('comercio__categoria').annotate(total=Count('id')).order_by('-total')

    if paradas_comercios.exists():
        max_paradas = max(p['total'] for p in paradas_comercios)
        for p in paradas_comercios[:5]:
            cat_nom = p['comercio__categoria'] or 'Otros'
            porc = int(round((p['total'] / max_paradas) * 100)) if max_paradas > 0 else 0
            impacto_comercial.append({
                'categoria': cat_nom[:16],
                'porcentaje': porc,
                'consumos': f"{p['total']} visita{'s' if p['total'] != 1 else ''}"
            })
    else:
        comercios_cats = ComercioAdherido.objects.values('categoria').annotate(
            total=Count('id')
        ).order_by('-total')

        if comercios_cats.exists():
            max_c = max(c['total'] for c in comercios_cats)
            for c in comercios_cats[:5]:
                cat_nom = c['categoria'] or 'Otros'
                porc = int(round((c['total'] / max_c) * 100)) if max_c > 0 else 0
                impacto_comercial.append({
                    'categoria': cat_nom[:16],
                    'porcentaje': porc,
                    'consumos': f"{c['total']} comercio{'s' if c['total'] != 1 else ''}"
                })
        else:
            cats_base = _get_categorias_comercio()
            for c in cats_base[:5]:
                impacto_comercial.append({
                    'categoria': c[:16],
                    'porcentaje': 0,
                    'consumos': '0 comercios'
                })

    # Serialización de etapas para el trazado del circuito activo
    subcircuitos_json = []
    if circuito_activo:
        for sub in circuito_activo.subcircuitos.all().order_by('orden'):
            puntos = list(sub.trazado.values('latitud', 'longitud').order_by('orden'))
            subcircuitos_json.append({
                'id': sub.id,
                'nombre': sub.nombre,
                'orden': sub.orden,
                'color': sub.color_capa,
                'coordenadas': [[float(p['latitud']), float(p['longitud'])] for p in puntos]
            })

    comercios_json = []
    if circuito_activo:
        for com in circuito_activo.comercios.all():
            comercios_json.append({
                'id': com.id,
                'nombre': com.nombre,
                'categoria': com.get_categoria_display(),
                'lat': float(com.latitud),
                'lng': float(com.longitud),
                'radio': com.radio_tolerancia_metros
            })

    context = {
        'admin_user': request.user,
        'total_participantes': f"{total_participantes:,}".replace(',', '.') if total_participantes > 0 else "0",
        'ciclistas_aprobados': ciclistas_aprobados,
        'ciclistas_pendientes': ciclistas_pendientes,
        'ciclistas_rechazados': ciclistas_rechazados,
        'circuitos_activos': circuitos_activos,
        'total_circuitos': total_circuitos,
        'total_comercios': total_comercios,
        'comercios_activos': comercios_activos,
        'comercios_revision': comercios_revision,
        'km_totales': km_totales_str,
        'total_recorridos': total_recorridos,
        'recorridos_en_curso': recorridos_en_curso,
        'circuito': circuito_activo,
        'total_etapas': total_etapas,
        'grafico': grafico_semanal,
        'actividad_reciente': actividad_reciente,
        'impacto_comercial': impacto_comercial,
        'subcircuitos_json': subcircuitos_json,
        'comercios_json': comercios_json,
    }
    return render(request, 'panel/dashboard.html', context)


def logout_admin_view(request):
    """
    Cierre de sesión administrativo y redirección al login interno.
    """
    por_inactividad = request.GET.get('inactividad') == '1'
    logout(request)
    if por_inactividad:
        messages.info(request, "Tu sesión administrativa ha expirado tras 1 hora de inactividad por motivos de seguridad.")
    else:
        messages.info(request, "Has cerrado sesión correctamente del Sistema Interno de Gestión.")
    return redirect('panel_login')


# ==============================================================================
# MÓDULO: GESTIÓN DE CICLISTAS
# ==============================================================================

@requiere_staff
def ciclistas_list_view(request):
    """
    Listado principal de ciclistas con búsqueda, filtros por estado y métricas.
    """
    queryset = Ciclista.objects.all().order_by('id')

    # Filtro por búsqueda de texto (Nombre, DNI, Email, Club o Código CIC-xxx)
    query = request.GET.get('q', '').strip()
    if query:
        # Si busca formato CIC-xxx o número
        id_query = None
        if query.upper().startswith('CIC-'):
            try:
                id_query = int(query.upper().replace('CIC-', ''))
            except ValueError:
                pass
        elif query.isdigit():
            id_query = int(query)

        filter_q = Q(nombre__icontains=query) | Q(dni__icontains=query) | Q(email__icontains=query) | Q(club_entidad__icontains=query)
        if id_query is not None:
            filter_q |= Q(id=id_query)

        queryset = queryset.filter(filter_q)

    # Filtro por Estado (Validado, Pendiente, Rechazado)
    estado_filtro = request.GET.get('estado', '').strip()
    if estado_filtro in ['Validado', 'Pendiente', 'Rechazado']:
        queryset = queryset.filter(estado=estado_filtro)

    # Métricas para tarjetas superiores
    total_db = Ciclista.objects.count()
    pendientes_db = Ciclista.objects.filter(estado='Pendiente').count()
    validados_db = Ciclista.objects.filter(estado__in=['Validado', 'Aprobado']).count()
    hoy_date = timezone.now().date()
    activos_hoy_db = RecorridoCiclista.objects.filter(inicio__date=hoy_date).values('ciclista').distinct().count()
    hace_7 = timezone.now() - timedelta(days=7)
    nuevos_semana_db = Ciclista.objects.filter(fecha_registro__gte=hace_7).count()

    context = {
        'ciclistas': queryset,
        'query': query,
        'estado_filtro': estado_filtro,
        'total_registrados': f"{total_db:,}".replace(',', '.') if total_db > 0 else "0",
        'pendientes_validacion': pendientes_db,
        'validados_total': validados_db,
        'activos_hoy': activos_hoy_db,
        'nuevos_semana': nuevos_semana_db,
    }
    return render(request, 'panel/gestion_ciclistas/listado_ciclistas.html', context)


@requiere_staff
def ciclista_create_view(request):
    """
    Formulario para registrar un nuevo ciclista en la plataforma municipal.
    """
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        dni = request.POST.get('dni', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        contacto_emergencia = request.POST.get('contacto_emergencia', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip() or None
        club_entidad = request.POST.get('club_entidad', 'Independiente').strip()
        nivel = request.POST.get('nivel', 'Aficionado')
        estado = request.POST.get('estado', 'Pendiente')
        observaciones = request.POST.get('observaciones', '').strip()
        foto = request.FILES.get('foto')
        clave_asignada = request.POST.get('clave_asignada', '').strip()

        # Validaciones de campos obligatorios
        if not nombre or not dni or not email:
            messages.error(request, "Por favor completa todos los campos obligatorios: Nombre, DNI y Correo Electrónico.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})

        # Validación de Fecha de Nacimiento (límite entre 10 y 90 años)
        if fecha_nacimiento:
            try:
                fn_date = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
                hoy = date.today()
                edad = hoy.year - fn_date.year - ((hoy.month, hoy.day) < (fn_date.month, fn_date.day))
                if edad < 10 or edad > 90:
                    messages.error(
                        request,
                        f"La edad del participante debe estar comprendida entre 10 y 90 años (edad calculada: {edad} años)."
                    )
                    return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})
            except (ValueError, TypeError):
                messages.error(request, "Por favor ingresa una fecha de nacimiento válida (AAAA-MM-DD).")
                return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})
        else:
            messages.error(request, "Por favor ingresa la fecha de nacimiento del participante.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})

        # Validación de Teléfono de Emergencia vs. Teléfono Personal
        tel_digitos = re.sub(r'\D', '', telefono)
        emerg_digitos = re.sub(r'\D', '', contacto_emergencia)
        if tel_digitos and emerg_digitos:
            if tel_digitos == emerg_digitos or (len(tel_digitos) >= 7 and len(emerg_digitos) >= 7 and (tel_digitos.endswith(emerg_digitos) or emerg_digitos.endswith(tel_digitos))):
                messages.error(
                    request,
                    "El número de teléfono de contacto de emergencia debe ser distinto al teléfono personal del ciclista."
                )
                return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})

        # Validaciones de duplicados
        if Ciclista.objects.filter(email__iexact=email).exists():
            messages.error(request, f"Ya existe un ciclista registrado con el correo {email}.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})

        if Ciclista.objects.filter(dni__iexact=dni).exists():
            messages.error(request, f"Ya existe un ciclista registrado con el DNI {dni}.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear', 'ciclista': request.POST})

        nuevo_ciclista = Ciclista.objects.create(
            nombre=nombre,
            email=email,
            dni=dni,
            fecha_nacimiento=fecha_nacimiento,
            telefono=telefono,
            contacto_emergencia=contacto_emergencia,
            club_entidad=club_entidad or "Independiente",
            nivel=nivel,
            estado=estado,
            observaciones=observaciones,
            foto=foto,
            clave_asignada=clave_asignada
        )

        if estado == 'Validado' and clave_asignada:
            user = User.objects.create_user(
                username=dni,
                email=email,
                password=clave_asignada,
                first_name=nombre[:30]
            )
            nuevo_ciclista.user = user
            nuevo_ciclista.save()

        messages.success(request, f"¡Ciclista {nuevo_ciclista.nombre} ({nuevo_ciclista.codigo_id}) registrado con éxito!")
        return redirect('panel_ciclistas_listado')

    return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'modo': 'crear'})


@requiere_staff
def ciclista_detail_view(request, pk):
    """
    Visualización técnica de la ficha completa del ciclista (modo lectura).
    """
    ciclista = get_object_or_404(Ciclista, pk=pk)
    return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {
        'ciclista': ciclista,
        'modo': 'ver'
    })


@requiere_staff
def ciclista_edit_view(request, pk):
    """
    Edición de datos del ciclista existente.
    Permite además al administrador actualizar la clave asignada y sincronizar la cuenta User.
    """
    ciclista = get_object_or_404(Ciclista, pk=pk)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        dni = request.POST.get('dni', '').strip()
        fecha_nac = request.POST.get('fecha_nacimiento', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        contacto_emergencia = request.POST.get('contacto_emergencia', '').strip()

        # Validaciones de campos obligatorios
        if not nombre or not dni or not email:
            messages.error(request, "Por favor completa todos los campos obligatorios: Nombre, DNI y Correo Electrónico.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})

        # Validación de Fecha de Nacimiento (límite entre 10 y 90 años)
        if fecha_nac:
            try:
                fn_date = datetime.strptime(fecha_nac, '%Y-%m-%d').date()
                hoy = date.today()
                edad = hoy.year - fn_date.year - ((hoy.month, hoy.day) < (fn_date.month, fn_date.day))
                if edad < 10 or edad > 90:
                    messages.error(
                        request,
                        f"La edad del participante debe estar comprendida entre 10 y 90 años (edad calculada: {edad} años)."
                    )
                    return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})
            except (ValueError, TypeError):
                messages.error(request, "Por favor ingresa una fecha de nacimiento válida (AAAA-MM-DD).")
                return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})
        else:
            messages.error(request, "Por favor ingresa la fecha de nacimiento del participante.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})

        # Validación de Teléfono de Emergencia vs. Personal
        tel_digitos = re.sub(r'\D', '', telefono)
        emerg_digitos = re.sub(r'\D', '', contacto_emergencia)
        if tel_digitos and emerg_digitos:
            if tel_digitos == emerg_digitos or (len(tel_digitos) >= 7 and len(emerg_digitos) >= 7 and (tel_digitos.endswith(emerg_digitos) or emerg_digitos.endswith(tel_digitos))):
                messages.error(
                    request,
                    "El número de teléfono de contacto de emergencia debe ser distinto al teléfono personal del ciclista."
                )
                return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})

        # Validaciones de duplicados excluyendo el propio ciclista
        if Ciclista.objects.filter(email__iexact=email).exclude(pk=ciclista.pk).exists():
            messages.error(request, f"Ya existe otro ciclista registrado con el correo {email}.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})

        if Ciclista.objects.filter(dni__iexact=dni).exclude(pk=ciclista.pk).exists():
            messages.error(request, f"Ya existe otro ciclista registrado con el DNI {dni}.")
            return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {'ciclista': ciclista, 'modo': 'editar'})

        ciclista.nombre = nombre
        ciclista.email = email
        ciclista.dni = dni
        ciclista.fecha_nacimiento = fn_date
        ciclista.telefono = telefono
        ciclista.contacto_emergencia = contacto_emergencia
        ciclista.club_entidad = request.POST.get('club_entidad', ciclista.club_entidad).strip()
        ciclista.nivel = request.POST.get('nivel', ciclista.nivel)
        ciclista.estado = request.POST.get('estado', ciclista.estado)
        ciclista.observaciones = request.POST.get('observaciones', ciclista.observaciones).strip()

        # Actualización de clave asignada (solo admin / staff)
        nueva_clave = request.POST.get('clave_asignada', '').strip()
        if nueva_clave and (request.user.is_superuser or request.user.is_staff):
            ciclista.clave_asignada = nueva_clave
            if ciclista.user:
                ciclista.user.set_password(nueva_clave)
                ciclista.user.save()
            elif ciclista.estado == 'Validado':
                user = User.objects.filter(Q(username=ciclista.dni) | Q(email__iexact=ciclista.email)).first()
                if not user:
                    user = User.objects.create_user(
                        username=ciclista.dni,
                        email=ciclista.email,
                        password=nueva_clave,
                        first_name=ciclista.nombre[:30]
                    )
                else:
                    user.set_password(nueva_clave)
                    user.save()
                ciclista.user = user

        if 'foto' in request.FILES:
            ciclista.foto = request.FILES['foto']

        ciclista.save()
        messages.success(request, f"Los datos de {ciclista.nombre} han sido actualizados correctamente.")
        return redirect('panel_ciclistas_listado')

    return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {
        'ciclista': ciclista,
        'modo': 'editar'
    })


@requiere_staff
def ciclista_delete_view(request, pk):
    """
    Eliminación definitiva de un ciclista del padrón municipal.
    """
    ciclista = get_object_or_404(Ciclista, pk=pk)
    if request.method == 'POST':
        nombre = ciclista.nombre
        codigo = ciclista.codigo_id
        ciclista.delete()
        messages.success(request, f"El ciclista {nombre} ({codigo}) fue eliminado correctamente del sistema.")
        return redirect('panel_ciclistas_listado')

    # Si se accede por GET, renderiza el formulario con confirmación
    return render(request, 'panel/gestion_ciclistas/form_ciclistas.html', {
        'ciclista': ciclista,
        'modo': 'eliminar'
    })


@requiere_staff
def ciclista_cambiar_estado_view(request, pk, nuevo_estado):
    """
    Permite al administrador municipal decidir sobre una solicitud de inscripción:
    aprobarla ('Validado') creando o activando su cuenta de usuario con credenciales con hash seguro,
    y almacenando la clave en el registro para soporte en caso de olvido.
    rechazarla ('Rechazado') o mantenerla 'Pendiente'.
    """
    ciclista = get_object_or_404(Ciclista, pk=pk)
    if nuevo_estado in ['Validado', 'Pendiente', 'Rechazado']:
        if nuevo_estado == 'Validado':
            # Obtener contraseña provista por el admin o generar una por defecto
            password = request.POST.get('password', '').strip()
            if not password:
                password = request.GET.get('password', '').strip()

            if not password:
                # Clave legible por defecto: Muni + últimos 4 dígitos del DNI (o 2026) + signo !
                ultimos_digitos = ''.join(c for c in ciclista.dni if c.isdigit())[-4:]
                if len(ultimos_digitos) < 4:
                    ultimos_digitos = '2026'
                password = f"Muni{ultimos_digitos}!"

            # Buscar o crear cuenta de usuario Django (con contraseña hasheada)
            user = ciclista.user
            if not user:
                user = User.objects.filter(
                    Q(username=ciclista.dni) | Q(email__iexact=ciclista.email)
                ).first()

            if user:
                user.username = ciclista.dni
                user.email = ciclista.email
                user.first_name = ciclista.nombre[:30]
                user.set_password(password)  # HASHEADA con PBKDF2/SHA256
                user.is_active = True
                user.save()
            else:
                user = User.objects.create_user(
                    username=ciclista.dni,
                    email=ciclista.email,
                    password=password,  # HASHEADA con PBKDF2/SHA256
                    first_name=ciclista.nombre[:30]
                )

            ciclista.user = user
            ciclista.clave_asignada = password  # GUARDADA legible solo para el Administrador
            ciclista.estado = 'Validado'
            ciclista.save()

            messages.success(
                request,
                f"¡Inscripción aprobada! El ciclista {ciclista.nombre} ({ciclista.codigo_id}) ha sido dado de alta. "
                f"Credenciales de acceso: Gmail/DNI: '{ciclista.email}' / '{ciclista.dni}' — Contraseña: '{password}'."
            )
        elif nuevo_estado == 'Rechazado':
            nombre_ciclista = ciclista.nombre
            codigo_ciclista = ciclista.codigo_id
            # Al rechazar, se elimina el registro del ciclista incluida su imagen física de media/ciclistas
            ciclista.delete()
            messages.warning(
                request,
                f"La solicitud de inscripción de {nombre_ciclista} ({codigo_ciclista}) ha sido RECHAZADA. "
                f"El registro y su imagen carnet han sido eliminados del sistema."
            )
        else:
            ciclista.estado = 'Pendiente'
            if ciclista.user:
                ciclista.user.is_active = False
                ciclista.user.save()
            ciclista.save()
            messages.info(
                request,
                f"El estado de {ciclista.nombre} ({ciclista.codigo_id}) ha sido restablecido a PENDIENTE de revisión."
            )
    return redirect('panel_ciclistas_listado')


@requiere_staff
def ciclistas_exportar_csv_view(request):
    """
    Exportación de ciclistas a formato CSV para planillas y auditoría municipal.
    """
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ciclistas_malagueno.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Nombre', 'Email', 'DNI', 'Club/Entidad', 'Nivel', 'Estado', 'Telefono', 'Fecha Registro'])

    for c in Ciclista.objects.all().order_by('id'):
        writer.writerow([
            c.codigo_id,
            c.nombre,
            c.email,
            c.dni,
            c.club_entidad,
            c.nivel,
            c.estado,
            c.telefono,
            c.fecha_registro.strftime('%Y-%m-%d %H:%M') if c.fecha_registro else ''
        ])

    return response


# ==============================================================================
# MÓDULO: GESTIÓN DE COMERCIOS
# ==============================================================================

@requiere_staff
def comercios_list_view(request):
    """
    Listado de establecimientos adheridos con búsqueda, filtros por estado y KPIs.
    """
    queryset = ComercioAdherido.objects.all().order_by('id')

    # Búsqueda por texto (Nombre, Dirección, Categoría)
    query = request.GET.get('q', '').strip()
    if query:
        queryset = queryset.filter(
            Q(nombre__icontains=query) |
            Q(direccion__icontains=query) |
            Q(categoria__icontains=query)
        )

    # Filtro por estado
    estado_filtro = request.GET.get('estado', '').strip()
    if estado_filtro:
        queryset = queryset.filter(estado=estado_filtro)

    # Métricas de KPIs de la imagen
    total = ComercioAdherido.objects.count()
    activos = ComercioAdherido.objects.filter(estado='Activo').count()
    en_revision = ComercioAdherido.objects.filter(Q(estado='En Revision') | Q(estado='En Revisión')).count()
    inactivos = ComercioAdherido.objects.filter(estado='Inactivo').count()

    context = {
        'comercios': queryset,
        'query': query,
        'estado_filtro': estado_filtro,
        'total_comercios': total,
        'activos': activos,
        'en_revision': en_revision,
        'inactivos': inactivos,
        'categorias_disponibles': _get_categorias_comercio(),
    }
    return render(request, 'panel/gestion_comercios/listado_comercios.html', context)


def _get_trazados_malagueno():
    """
    Obtiene las etapas y coordenadas del circuito activo para dibujarlas de fondo en el mapa.
    """
    circuito = CircuitoGeneral.objects.filter(activo=True).first()
    trazados = []
    if circuito:
        for sub in circuito.subcircuitos.all().order_by('orden'):
            pts = list(sub.trazado.all().order_by('orden').values_list('latitud', 'longitud'))
            if pts:
                trazados.append({
                    'id': sub.id,
                    'nombre': sub.nombre,
                    'color': sub.color_capa,
                    'orden': sub.orden,
                    'coordenadas': [[float(p[0]), float(p[1])] for p in pts]
                })
    return trazados


@requiere_staff
def comercio_create_view(request):
    """
    Creación de un nuevo comercio o punto de abastecimiento adherido en Malagueño.
    """
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        categoria = request.POST.get('categoria', 'Restauración')
        estado = request.POST.get('estado', 'Activo')
        latitud = request.POST.get('latitud', '-31.464500')
        longitud = request.POST.get('longitud', '-64.362000')
        radio = request.POST.get('radio_tolerancia_metros', '30')
        telefono = request.POST.get('telefono', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        imagen = request.FILES.get('imagen')

        circuito_activo = CircuitoGeneral.objects.filter(activo=True).first()

        nuevo_comercio = ComercioAdherido.objects.create(
            circuito_general=circuito_activo,
            nombre=nombre,
            direccion=direccion,
            categoria=categoria,
            estado=estado,
            latitud=float(latitud),
            longitud=float(longitud),
            radio_tolerancia_metros=int(radio),
            telefono=telefono,
            descripcion=descripcion,
            imagen=imagen
        )
        messages.success(request, f"¡Comercio '{nuevo_comercio.nombre}' registrado con éxito en Malagueño!")
        return redirect('panel_comercios_listado')

    return render(request, 'panel/gestion_comercios/form_comercios.html', {
        'modo': 'crear',
        'categorias_disponibles': _get_categorias_comercio(),
        'trazado_json': json.dumps(_get_trazados_malagueno())
    })


@requiere_staff
def comercio_detail_view(request, pk):
    """
    Ficha técnica del comercio con mapa interactivo y coordenadas (modo lectura).
    """
    comercio = get_object_or_404(ComercioAdherido, pk=pk)
    return render(request, 'panel/gestion_comercios/form_comercios.html', {
        'comercio': comercio,
        'modo': 'ver',
        'categorias_disponibles': _get_categorias_comercio(),
        'trazado_json': json.dumps(_get_trazados_malagueno())
    })


@requiere_staff
def comercio_edit_view(request, pk):
    """
    Edición de datos, coordenadas y radio de tolerancia del comercio.
    """
    comercio = get_object_or_404(ComercioAdherido, pk=pk)

    if request.method == 'POST':
        comercio.nombre = request.POST.get('nombre', comercio.nombre).strip()
        comercio.direccion = request.POST.get('direccion', comercio.direccion).strip()
        comercio.categoria = request.POST.get('categoria', comercio.categoria)
        comercio.estado = request.POST.get('estado', comercio.estado)
        comercio.latitud = float(request.POST.get('latitud', comercio.latitud))
        comercio.longitud = float(request.POST.get('longitud', comercio.longitud))
        comercio.radio_tolerancia_metros = int(request.POST.get('radio_tolerancia_metros', comercio.radio_tolerancia_metros))
        comercio.telefono = request.POST.get('telefono', comercio.telefono).strip()
        comercio.descripcion = request.POST.get('descripcion', comercio.descripcion).strip()

        if 'imagen' in request.FILES:
            # Si ya existía una imagen anterior, la eliminamos físicamente del disco
            if comercio.imagen:
                try:
                    if os.path.isfile(comercio.imagen.path):
                        os.remove(comercio.imagen.path)
                except Exception:
                    pass
            comercio.imagen = request.FILES['imagen']
        elif request.POST.get('eliminar_imagen') == '1':
            if comercio.imagen:
                try:
                    if os.path.isfile(comercio.imagen.path):
                        os.remove(comercio.imagen.path)
                except Exception:
                    pass
                comercio.imagen = None

        comercio.save()
        messages.success(request, f"Los datos de '{comercio.nombre}' se actualizaron correctamente.")
        return redirect('panel_comercios_listado')

    return render(request, 'panel/gestion_comercios/form_comercios.html', {
        'comercio': comercio,
        'modo': 'editar',
        'categorias_disponibles': _get_categorias_comercio(),
        'trazado_json': json.dumps(_get_trazados_malagueno())
    })


@requiere_staff
def comercio_delete_view(request, pk):
    """
    Eliminación de un comercio de la red municipal.
    """
    comercio = get_object_or_404(ComercioAdherido, pk=pk)
    if request.method == 'POST':
        nombre = comercio.nombre
        comercio.delete()
        messages.success(request, f"El establecimiento '{nombre}' fue eliminado correctamente.")
        return redirect('panel_comercios_listado')

    return render(request, 'panel/gestion_comercios/form_comercios.html', {
        'comercio': comercio,
        'modo': 'eliminar'
    })


# ==============================================================================
# MÓDULO: GESTIÓN DE CIRCUITOS Y TRAZADOR DE ETAPAS
# ==============================================================================

@requiere_staff
def circuitos_list_view(request):
    """
    Listado institucional de circuitos generales, etapas activas y comercios asociados.
    """
    circuitos = CircuitoGeneral.objects.all().prefetch_related('subcircuitos', 'comercios')

    total_circuitos = circuitos.count()
    circuitos_activos = circuitos.filter(activo=True).count()
    circuito_activo = circuitos.filter(activo=True).first()
    total_subcircuitos = SubCircuito.objects.count()
    total_comercios_en_circuito = ComercioAdherido.objects.filter(circuito_general__isnull=False).count()

    context = {
        'circuitos': circuitos,
        'total_circuitos': total_circuitos,
        'circuitos_activos': circuitos_activos,
        'circuito_activo': circuito_activo,
        'total_subcircuitos': total_subcircuitos,
        'total_comercios_en_circuito': total_comercios_en_circuito,
    }
    return render(request, 'panel/gestion_circuitos/listado_circuitos.html', context)


@requiere_staff
def circuito_editor_view(request, pk=None):
    """
    Editor Todo-en-Uno (estilo Google My Maps) para crear o editar un circuito,
    dibujar sus etapas sobre el mapa satelital de Malagueño y adherir comercios.
    """
    circuito = None
    subcircuitos_data = []

    if pk:
        circuito = get_object_or_404(CircuitoGeneral, pk=pk)
        for sub in circuito.subcircuitos.all().order_by('orden'):
            coords = list(sub.trazado.all().order_by('orden').values_list('latitud', 'longitud'))
            subcircuitos_data.append({
                'id': sub.id,
                'nombre': sub.nombre,
                'orden': sub.orden,
                'color_capa': sub.color_capa,
                'coordenadas': [[float(c[0]), float(c[1])] for c in coords]
            })

    # Comercios de Malagueño disponibles para adherir
    comercios_data = []
    for com in ComercioAdherido.objects.all().order_by('nombre'):
        adherido = bool(circuito and com.circuito_general_id == circuito.id)
        comercios_data.append({
            'id': com.id,
            'nombre': com.nombre,
            'categoria': com.categoria,
            'lat': float(com.latitud),
            'lng': float(com.longitud),
            'radio': com.radio_tolerancia_metros,
            'adherido': adherido,
            'subcircuito_id': com.subcircuito_id if (adherido and com.subcircuito_id) else None
        })

    context = {
        'circuito': circuito,
        'subcircuitos_json': json.dumps(subcircuitos_data),
        'comercios_json': json.dumps(comercios_data),
        'tipos_movilidad': TIPOS_MOVILIDAD,
        'dificultades_circuito': DIFICULTADES_CIRCUITO,
    }
    return render(request, 'panel/gestion_circuitos/editor_circuito.html', context)


@requiere_staff
def circuito_guardar_api_view(request):
    """
    API endpoint para guardar atómicamente el circuito, etapas/polilíneas y comercios adheridos.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        circuito_id = data.get('circuito_id')
        nombre = data.get('nombre', '').strip()
        descripcion = data.get('descripcion', '').strip()
        dificultad = data.get('dificultad', 'MODERADO').strip().upper()
        if dificultad not in dict(DIFICULTADES_CIRCUITO):
            dificultad = 'MODERADO'
        activo = bool(data.get('activo', False))
        radio_largada_metros = int(data.get('radio_largada_metros') or 80)
        movilidades_raw = data.get('movilidades_permitidas', [])
        if isinstance(movilidades_raw, list):
            movilidades_str = ",".join([m for m in movilidades_raw if m])
        elif isinstance(movilidades_raw, str):
            movilidades_str = movilidades_raw
        else:
            movilidades_str = "BICICLETA"
        if not movilidades_str:
            movilidades_str = "BICICLETA"

        etapas_data = data.get('etapas', [])
        comercios_adheridos = data.get('comercios_adheridos', [])

        if not nombre:
            return JsonResponse({'ok': False, 'error': 'El nombre del circuito es obligatorio.'}, status=400)

        with transaction.atomic():
            # 1. Crear o actualizar CircuitoGeneral
            if circuito_id:
                circuito = get_object_or_404(CircuitoGeneral, pk=circuito_id)
                circuito.nombre = nombre
                circuito.descripcion = descripcion
                circuito.dificultad = dificultad
                circuito.activo = activo
                circuito.radio_largada_metros = radio_largada_metros
                circuito.movilidades_permitidas = movilidades_str
                circuito.save()
            else:
                circuito = CircuitoGeneral.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    dificultad=dificultad,
                    activo=activo,
                    radio_largada_metros=radio_largada_metros,
                    movilidades_permitidas=movilidades_str
                )

            # 2. Guardar Etapas / Subcircuitos
            etapas_ids_vigentes = []
            etapa_id_map = {} # mapping temp_id -> SubCircuito real

            for idx, et in enumerate(etapas_data):
                et_id = et.get('id')
                et_nombre = et.get('nombre', f'Etapa {idx+1}').strip()
                et_orden = idx + 1
                et_color = et.get('color_capa', '#10b981')
                coordenadas = et.get('coordenadas', [])

                if et_id and str(et_id).isdigit():
                    sub = SubCircuito.objects.filter(id=int(et_id), circuito_general=circuito).first()
                    if sub:
                        sub.nombre = et_nombre
                        sub.orden = et_orden
                        sub.color_capa = et_color
                        sub.save()
                    else:
                        sub = SubCircuito.objects.create(
                            circuito_general=circuito,
                            nombre=et_nombre,
                            orden=et_orden,
                            color_capa=et_color
                        )
                else:
                    sub = SubCircuito.objects.create(
                        circuito_general=circuito,
                        nombre=et_nombre,
                        orden=et_orden,
                        color_capa=et_color
                    )

                etapas_ids_vigentes.append(sub.id)
                etapa_id_map[str(et_id)] = sub
                etapa_id_map[str(sub.id)] = sub

                # Recrear PuntosTramo
                sub.trazado.all().delete()
                nuevos_puntos = []
                for p_idx, coord in enumerate(coordenadas):
                    nuevos_puntos.append(PuntosTramo(
                        subcircuito=sub,
                        orden=p_idx + 1,
                        latitud=float(coord[0]),
                        longitud=float(coord[1])
                    ))
                if nuevos_puntos:
                    PuntosTramo.objects.bulk_create(nuevos_puntos)

            # Eliminar subcircuitos que ya no estén en la lista
            circuito.subcircuitos.exclude(id__in=etapas_ids_vigentes).delete()

            # 3. Guardar Comercios Adheridos
            # Desasociar comercios que antes pertenecían a este circuito y ya no están adheridos
            comercios_adheridos_ids = [c['id'] for c in comercios_adheridos if 'id' in c]
            ComercioAdherido.objects.filter(circuito_general=circuito).exclude(id__in=comercios_adheridos_ids).update(
                circuito_general=None,
                subcircuito=None
            )

            # Asociar los comercios seleccionados
            for c_info in comercios_adheridos:
                cid = c_info.get('id')
                sub_ref = c_info.get('subcircuito_id')

                com = ComercioAdherido.objects.filter(id=cid).first()
                if com:
                    com.circuito_general = circuito

                    # Asignar subcircuito si corresponde
                    sub_obj = None
                    if sub_ref:
                        if str(sub_ref) in etapa_id_map:
                            sub_obj = etapa_id_map[str(sub_ref)]
                        elif str(sub_ref).isdigit():
                            sub_obj = SubCircuito.objects.filter(id=int(sub_ref), circuito_general=circuito).first()

                    com.subcircuito = sub_obj
                    com.save()

        messages.success(request, f"¡El circuito '{circuito.nombre}' y sus etapas fueron guardados correctamente!")
        return JsonResponse({'ok': True, 'circuito_id': circuito.id})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@requiere_staff
def circuito_activar_view(request, pk):
    """
    Alterna o activa el estado del circuito seleccionado para publicarlo o pausarlo en la plataforma,
    permitiendo la coexistencia de múltiples circuitos habilitados simultáneamente.
    """
    circuito = get_object_or_404(CircuitoGeneral, pk=pk)
    if circuito.activo:
        circuito.activo = False
        circuito.save()
        messages.info(request, f"El circuito '{circuito.nombre}' ha sido pausado y ocultado del portal ciclista.")
    else:
        circuito.activo = True
        circuito.save()
        messages.success(request, f"¡El circuito '{circuito.nombre}' ha sido activado y publicado para los ciclistas!")
    return redirect('panel_circuitos_listado')


@requiere_staff
def circuito_delete_view(request, pk):
    """
    Eliminación definitiva de un circuito y sus etapas asociadas.
    """
    circuito = get_object_or_404(CircuitoGeneral, pk=pk)
    nombre = circuito.nombre
    circuito.delete()
    messages.success(request, f"El circuito '{nombre}' fue eliminado correctamente.")
    return redirect('panel_circuitos_listado')


# ==============================================================================
# 5. MÓDULO DE GESTIÓN DE NOTICIAS Y COMUNICADOS
# ==============================================================================

@requiere_staff
def noticias_list_view(request):
    """
    Listado y administración de noticias y comunicados oficiales.
    Permite filtrar por estado (Publicadas, Borradores, Archivadas), por texto y por categoría.
    Diseñado fiel a la maqueta de referencia institucional (Visily).
    """
    noticias_qs = Noticia.objects.all().order_by('-fecha_publicacion')

    # Filtro por Estado (Todas, Publicado, Borrador, Archivado)
    estado_filtro = request.GET.get('estado', '').strip()
    if estado_filtro in ['Publicado', 'Borrador', 'Archivado']:
        noticias_qs = noticias_qs.filter(estado=estado_filtro)

    # Filtro por Categoría
    categoria_filtro = request.GET.get('categoria', '').strip()
    if categoria_filtro:
        noticias_qs = noticias_qs.filter(categoria=categoria_filtro)

    # Búsqueda por texto (título, contenido o autor)
    query_q = request.GET.get('q', '').strip()
    if query_q:
        noticias_qs = noticias_qs.filter(
            Q(titulo__icontains=query_q) |
            Q(contenido__icontains=query_q) |
            Q(autor_nombre__icontains=query_q)
        )

    # Métricas y KPIs de la cabecera
    total_publicadas = Noticia.objects.filter(estado='Publicado').count()
    total_borradores = Noticia.objects.filter(estado='Borrador').count()
    total_archivadas = Noticia.objects.filter(estado='Archivado').count()
    vistas_sum = Noticia.objects.aggregate(total=Sum('vistas'))['total'] or 0
    lecturas_hoy = f"{vistas_sum:,}".replace(',', '.') if vistas_sum > 0 else "0"

    # Paginación
    total_resultados = noticias_qs.count()
    paginator = Paginator(noticias_qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    categorias_disponibles = Noticia.CATEGORIAS

    context = {
        'noticias': page_obj,
        'page_obj': page_obj,
        'total_resultados': total_resultados,
        'total_publicadas': total_publicadas,
        'total_borradores': total_borradores,
        'total_archivadas': total_archivadas,
        'lecturas_hoy': lecturas_hoy,
        'estado_filtro': estado_filtro,
        'categoria_filtro': categoria_filtro,
        'query_q': query_q,
        'categorias_disponibles': categorias_disponibles,
    }
    return render(request, 'panel/gestion_noticias/listado_noticias.html', context)


@requiere_staff
def noticia_create_view(request):
    """
    Creación de una nueva noticia o comunicado oficial municipal.
    """
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        categoria = request.POST.get('categoria', 'Comunidad').strip()
        autor_nombre = request.POST.get('autor_nombre', '').strip()
        estado = request.POST.get('estado', 'Publicado').strip()
        contenido = request.POST.get('contenido', '').strip()
        imagen = request.FILES.get('imagen')

        if not titulo or not contenido:
            messages.error(request, "El título y el contenido son obligatorios.")
            return render(request, 'panel/gestion_noticias/form_noticias.html', {
                'noticia': None,
                'request_post': request.POST
            })

        noticia = Noticia.objects.create(
            titulo=titulo,
            categoria=categoria,
            autor=request.user if request.user.is_authenticated else None,
            autor_nombre=autor_nombre,
            estado=estado,
            contenido=contenido,
            imagen=imagen
        )

        messages.success(request, f"¡La noticia '{noticia.titulo}' fue creada con éxito en estado {noticia.estado}!")
        return redirect('panel_noticias_listado')

    return render(request, 'panel/gestion_noticias/form_noticias.html', {'noticia': None})


@requiere_staff
def noticia_edit_view(request, pk):
    """
    Edición de una noticia o comunicado existente.
    """
    noticia = get_object_or_404(Noticia, pk=pk)

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        categoria = request.POST.get('categoria', 'Comunidad').strip()
        autor_nombre = request.POST.get('autor_nombre', '').strip()
        estado = request.POST.get('estado', 'Publicado').strip()
        contenido = request.POST.get('contenido', '').strip()
        imagen = request.FILES.get('imagen')
        eliminar_imagen = request.POST.get('eliminar_imagen') == '1'

        if not titulo or not contenido:
            messages.error(request, "El título y el contenido son obligatorios.")
            return render(request, 'panel/gestion_noticias/form_noticias.html', {'noticia': noticia})

        noticia.titulo = titulo
        noticia.categoria = categoria
        noticia.autor_nombre = autor_nombre
        noticia.estado = estado
        noticia.contenido = contenido

        if imagen:
            noticia.imagen = imagen
        elif eliminar_imagen:
            noticia.imagen = None

        noticia.save()
        messages.success(request, f"¡La noticia '{noticia.titulo}' ha sido actualizada correctamente!")
        return redirect('panel_noticias_listado')

    return render(request, 'panel/gestion_noticias/form_noticias.html', {'noticia': noticia})


@requiere_staff
def noticia_delete_view(request, pk):
    """
    Eliminación definitiva de una noticia.
    """
    noticia = get_object_or_404(Noticia, pk=pk)
    titulo = noticia.titulo
    noticia.delete()
    messages.success(request, f"La noticia '{titulo}' fue eliminada permanentemente.")
    return redirect('panel_noticias_listado')


@requiere_staff
def noticia_cambiar_estado_view(request, pk, nuevo_estado):
    """
    Cambio ágil de estado (Publicado, Borrador, Archivado) desde la tabla de noticias.
    """
    noticia = get_object_or_404(Noticia, pk=pk)
    if nuevo_estado in ['Publicado', 'Borrador', 'Archivado']:
        noticia.estado = nuevo_estado
        noticia.save()
        messages.success(request, f"Estado de '{noticia.titulo}' cambiado a {nuevo_estado}.")
    return redirect('panel_noticias_listado')


@requiere_staff
def ranking_evento_view(request, circuito_id=None):
    """
    Vista de Ranking y Estadísticas de Circuitos para el Panel Municipal.
    Permite filtrar por circuito y visualizar métricas avanzadas: podio, mejores marcas,
    velocidad máxima, paradas en comercios y tiempos por tramo.
    """
    todos_circuitos = CircuitoGeneral.objects.filter(activo=True).order_by('nombre')

    # Seleccionar circuito actual
    if not circuito_id:
        circuito_id = request.GET.get('circuito_id')

    circuito_actual = None
    if circuito_id:
        circuito_actual = CircuitoGeneral.objects.filter(id=circuito_id).first()

    if not circuito_actual:
        circuito_actual = todos_circuitos.first()

    # Filtrar recorridos finalizados del circuito
    recorridos_qs = RecorridoCiclista.objects.filter(
        circuito=circuito_actual,
        estado='FINALIZADO'
    ).select_related('ciclista')

    # 3. Procesar datos de participantes y telemetría agrupando por el MEJOR TIEMPO único de cada participante
    mejores_por_ciclista = {}

    for r in recorridos_qs:
        # Tiempo total transcurrido
        segundos = 0
        tiempo_formateado = "--:--:--"
        if r.inicio and r.fin:
            delta = (r.fin - r.inicio).total_seconds()
            if delta > 0:
                segundos = int(delta)
                horas = segundos // 3600
                minutos = (segundos % 3600) // 60
                segs = segundos % 60
                tiempo_formateado = f"{horas:02d}:{minutos:02d}:{segs:02d}"

        ciclista_id = r.ciclista_id

        # Si el ciclista ya tiene un récord registrado, conservar el de menor tiempo > 0
        if ciclista_id in mejores_por_ciclista:
            anterior = mejores_por_ciclista[ciclista_id]
            es_mejor = (anterior['segundos'] == 0 and segundos > 0) or (segundos > 0 and segundos < anterior['segundos'])
            if not es_mejor:
                continue

        # Perfil del ciclista
        ciclista_obj = Ciclista.objects.filter(user=r.ciclista).first()
        nombre_completo = f"{r.ciclista.first_name} {r.ciclista.last_name}".strip() or r.ciclista.username
        if ciclista_obj:
            nombre_completo = ciclista_obj.nombre or nombre_completo
            dni = ciclista_obj.dni or r.ciclista.username
            nivel = ciclista_obj.nivel or 'Recreativo'
            club = ciclista_obj.club_entidad or 'Independiente'
        else:
            dni = r.ciclista.username
            nivel = 'Recreativo'
            club = 'Independiente'

        # Distancia y velocidad promedio
        distancia_km = float(r.distancia_km or 0.0)
        velocidad_prom_kmh = 0.0
        if segundos > 0 and distancia_km > 0:
            velocidad_prom_kmh = round((distancia_km / (segundos / 3600.0)), 1)

        # Velocidad máxima de la telemetría GPS (calculada por deltas de tramos GPS consecutivos)
        vel_max_kmh = velocidad_prom_kmh
        puntos_gps = list(r.puntos.order_by('timestamp').values('latitud', 'longitud', 'timestamp'))
        if len(puntos_gps) >= 2:
            max_v = 0.0
            for i in range(len(puntos_gps) - 1):
                p_a, p_b = puntos_gps[i], puntos_gps[i + 1]
                t_a, t_b = p_a['timestamp'], p_b['timestamp']
                if t_a and t_b:
                    dt = (t_b - t_a).total_seconds()
                    if 1.0 <= dt <= 30.0:
                        d_m = calcular_distancia_metros(p_a['latitud'], p_a['longitud'], p_b['latitud'], p_b['longitud'])
                        v_kmh = (d_m / dt) * 3.6
                        if 0 < v_kmh < 95.0 and v_kmh > max_v:
                            max_v = v_kmh
            if max_v > 0:
                vel_max_kmh = round(max(max_v, velocidad_prom_kmh), 1)
        elif velocidad_prom_kmh > 0:
            vel_max_kmh = round(velocidad_prom_kmh * 1.15, 1)

        # Cantidad de paradas y comercios validados
        paradas_count = ParadaRecorrido.objects.filter(recorrido=r).count()
        comercios_count = ParadaRecorrido.objects.filter(recorrido=r, es_comercio_adherido=True).count()

        mejores_por_ciclista[ciclista_id] = {
            'recorrido': r,
            'ciclista_id': ciclista_id,
            'ciclista_nombre': nombre_completo,
            'dni': dni,
            'nivel': nivel,
            'club': club,
            'dorsal_str': f"#{r.id:04d}",
            'segundos': segundos,
            'tiempo_str': tiempo_formateado,
            'distancia_km': distancia_km,
            'velocidad_prom': velocidad_prom_kmh,
            'velocidad_max': vel_max_kmh,
            'paradas': paradas_count,
            'comercios': comercios_count,
            'tipo_movilidad': r.tipo_movilidad or 'BICICLETA',
            'tipo_movilidad_display': r.get_tipo_movilidad_display() if hasattr(r, 'get_tipo_movilidad_display') else (r.tipo_movilidad or 'Bicicleta'),
            'fecha': r.inicio.strftime("%d/%m/%Y %H:%M") if r.inicio else ""
        }

    participantes_data = list(mejores_por_ciclista.values())

    # 4. Ordenar participantes por tiempo de menor a mayor (ranking)
    participantes_data.sort(key=lambda x: (x['segundos'] == 0, x['segundos']))

    # Asignar posición en el ranking
    for idx, p in enumerate(participantes_data, start=1):
        p['posicion'] = idx

    # 5. Podio (Top 3)
    podio = participantes_data[:3] if len(participantes_data) >= 1 else []

    # 6. Estadísticas Generales del Circuito y Uso Ciudadano
    total_finalizados = len(participantes_data)
    total_iniciados = RecorridoCiclista.objects.filter(circuito=circuito_actual).count() if circuito_actual else 0
    ciclistas_unicos = RecorridoCiclista.objects.filter(circuito=circuito_actual).values('ciclista').distinct().count() if circuito_actual else 0

    mejor_tiempo = participantes_data[0]['tiempo_str'] if participantes_data and participantes_data[0]['segundos'] > 0 else "--:--:--"
    velocidad_max_evento = max([p['velocidad_max'] for p in participantes_data], default=0.0)
    velocidad_prom_evento = round(sum([p['velocidad_prom'] for p in participantes_data]) / total_finalizados, 1) if total_finalizados > 0 else 0.0

    # Subcircuitos / Tramos del circuito actual
    subcircuitos = SubCircuito.objects.filter(circuito_general=circuito_actual).order_by('orden') if circuito_actual else []

    context = {
        'circuito': circuito_actual,
        'todos_circuitos': todos_circuitos,
        'participantes': participantes_data,
        'podio': podio,
        'total_iniciados': total_iniciados,
        'total_finalizados': total_finalizados,
        'ciclistas_unicos': ciclistas_unicos,
        'mejor_tiempo': mejor_tiempo,
        'velocidad_max_evento': velocidad_max_evento,
        'velocidad_prom_evento': velocidad_prom_evento,
        'subcircuitos': subcircuitos,
    }
    return render(request, 'panel/ranking_evento.html', context)




