"""
Vistas de API REST para ingesta de telemetría GPS, consulta de circuitos y monitoreo.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, date

from .models import (
    CircuitoGeneral,
    SubCircuito,
    PuntosTramo,
    ComercioAdherido,
    RecorridoCiclista,
    ParadaRecorrido,
    RegistroGPS,
    Noticia
)
from .serializers import (
    CircuitoGeneralSerializer,
    SubCircuitoSerializer,
    ComercioAdheridoSerializer,
    BatchGPSInputSerializer,
    RegistroGPSSerializer,
    RecorridoCiclistaSerializer,
    NoticiaSerializer
)
from .utils import (
    calcular_distancia_metros,
    evaluar_parada_comercio,
    calcular_distancia_total_puntos
)


class CircuitoActivoAPIView(APIView):
    """
    GET /api/circuitos/activo/?circuito_id=X
    Devuelve la geometría y datos del circuito activo solicitado (o el principal si no se pasa ID)
    para renderizado dinámico en Leaflet.
    Accesible públicamente sin autenticación.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        circuito_id = request.query_params.get('circuito_id')
        if circuito_id:
            circuito = CircuitoGeneral.objects.filter(id=circuito_id, activo=True).prefetch_related(
                'subcircuitos__trazado',
                'comercios'
            ).first()
        else:
            today = date.today()
            circuitos_qs = CircuitoGeneral.objects.filter(activo=True).prefetch_related(
                'subcircuitos__trazado',
                'comercios'
            )
            # Priorizar evento oficial vigente o primer circuito activo
            circuito = circuitos_qs.filter(fecha_evento__gte=today).order_by('fecha_evento').first() or circuitos_qs.first()

        if not circuito:
            return Response(
                {"mensaje": "No hay ningún circuito marcado como activo en este momento."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CircuitoGeneralSerializer(circuito)
        return Response(serializer.data, status=status.HTTP_200_OK)


class IniciarRecorridoAPIView(APIView):
    """
    POST /api/recorrido/iniciar/
    Inicia o reanuda un recorrido para el ciclista autenticado.
    Valida que la posición GPS actual del ciclista coincida dentro del radio de largada del circuito.
    Determina si la modalidad es OFICIAL (si coincide con la fecha del evento) o LIBRE (práctica).
    Payload opcional: { "circuito_id": 1, "latitud": -31.468, "longitud": -64.355 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        circuito_id = request.data.get('circuito_id')
        latitud = request.data.get('latitud')
        longitud = request.data.get('longitud')

        if circuito_id:
            circuito = get_object_or_404(CircuitoGeneral, id=circuito_id)
        else:
            circuito = CircuitoGeneral.objects.filter(activo=True).first()
            if not circuito:
                return Response(
                    {"error": "No hay ningún circuito activo configurado."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validación del punto de largada si el circuito tiene trazado y se envían coordenadas
        punto_inicio = circuito.punto_largada
        radio_maximo = circuito.radio_largada_metros or 20

        if punto_inicio and latitud is not None and longitud is not None:
            distancia_a_largada = calcular_distancia_metros(
                latitud, longitud,
                punto_inicio[0], punto_inicio[1]
            )

            if distancia_a_largada > radio_maximo:
                return Response(
                    {
                        "fuera_de_radio": True,
                        "error": (
                            f"Estás a {int(distancia_a_largada)} metros del punto de largada. "
                            f"Debes acercarte a menos de {radio_maximo} metros del Km 0 para iniciar."
                        ),
                        "distancia_metros": round(distancia_a_largada, 1),
                        "radio_permitido": radio_maximo,
                        "punto_largada": {
                            "lat": punto_inicio[0],
                            "lng": punto_inicio[1]
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Determinar si hoy es el día del evento oficial y modo solicitado
        es_dia_carrera = bool(circuito.fecha_evento and circuito.fecha_evento == date.today())
        modo_solicitado = (request.data.get('modo') or '').strip().lower()

        # Verificar si el ciclista está inscripto a la carrera oficial
        inscripcion_oficial = RecorridoCiclista.objects.filter(
            ciclista=request.user,
            circuito=circuito,
            modalidad='OFICIAL'
        ).first()

        if es_dia_carrera and inscripcion_oficial and modo_solicitado != 'libre':
            # Carrera Oficial: activar la manga de carrera del participante
            modalidad = 'OFICIAL'
            recorrido = inscripcion_oficial
            recorrido.estado = 'EN_CURSO'
            recorrido.save()
            creado = False
        else:
            # Modo Libre: práctica, reconocimiento o paseo recreativo sin alterar la inscripción
            modalidad = 'LIBRE'
            recorrido = RecorridoCiclista.objects.filter(
                ciclista=request.user,
                circuito=circuito,
                modalidad='LIBRE',
                estado__in=['EN_CURSO', 'PAUSADO']
            ).first()

            if recorrido:
                recorrido.estado = 'EN_CURSO'
                recorrido.save()
                creado = False
            else:
                recorrido = RecorridoCiclista.objects.create(
                    ciclista=request.user,
                    circuito=circuito,
                    estado='EN_CURSO',
                    modalidad='LIBRE'
                )
                creado = True

        serializer = RecorridoCiclistaSerializer(recorrido)
        return Response(
            {
                "mensaje": "Recorrido iniciado con éxito" if creado else "Recorrido reanudado",
                "recorrido": serializer.data,
                "modalidad": recorrido.modalidad,
                "circuito_nombre": circuito.nombre
            },
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK
        )


class RegistrarParadaAPIView(APIView):
    """
    POST /api/recorrido/detener/
    Registra una detención puntual (botón táctil 'DETENER') en la coordenada actual del ciclista.
    Evalúa si la parada coincide con el radio de tolerancia de algún comercio adherido,
    punto de hidratación o asistencia técnica.
    Pausa el recorrido activo del ciclista.
    Payload: { "recorrido_id": 102, "latitud": -31.468, "longitud": -64.355 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        recorrido_id = request.data.get('recorrido_id')
        latitud = request.data.get('latitud')
        longitud = request.data.get('longitud')

        if not recorrido_id:
            return Response(
                {"error": "Debe especificar el recorrido_id"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if latitud is None or longitud is None:
            return Response(
                {"error": "Debe enviar las coordenadas (latitud y longitud) del punto de frenado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        recorrido = get_object_or_404(
            RecorridoCiclista.objects.select_related('circuito'),
            id=recorrido_id,
            ciclista=request.user
        )

        # 1. Pausar el recorrido
        recorrido.estado = 'PAUSADO'
        recorrido.save()

        # 2. Evaluar proximidad con comercios / puntos adheridos del circuito
        comercios = list(recorrido.circuito.comercios.all())
        parada_comercio = evaluar_parada_comercio(latitud, longitud, comercios)

        comercio_obj = None
        es_comercio = False
        nombre_parada = "Parada Técnica / Descanso"

        if parada_comercio:
            es_comercio = True
            nombre_parada = parada_comercio['nombre']
            try:
                comercio_obj = ComercioAdherido.objects.get(id=parada_comercio['id'])
            except ComercioAdherido.DoesNotExist:
                comercio_obj = None

        # 3. Guardar registro en ParadaRecorrido
        parada = ParadaRecorrido.objects.create(
            recorrido=recorrido,
            comercio=comercio_obj,
            latitud=latitud,
            longitud=longitud,
            es_comercio_adherido=es_comercio,
            nombre_parada=nombre_parada
        )

        return Response(
            {
                "status": "ok",
                "estado": "PAUSADO",
                "parada_id": parada.id,
                "es_comercio_adherido": es_comercio,
                "nombre_parada": nombre_parada,
                "comercio": parada_comercio,
                "timestamp": parada.timestamp
            },
            status=status.HTTP_201_CREATED
        )


class PausarRecorridoAPIView(APIView):
    """
    POST /api/recorrido/pausar/
    Pausa el recorrido activo del ciclista.
    Payload: { "recorrido_id": 102 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        recorrido_id = request.data.get('recorrido_id')
        if not recorrido_id:
            return Response({"error": "Debe especificar recorrido_id"}, status=status.HTTP_400_BAD_REQUEST)

        recorrido = get_object_or_404(RecorridoCiclista, id=recorrido_id, ciclista=request.user)
        recorrido.estado = 'PAUSADO'
        recorrido.save()

        return Response({"status": "ok", "estado": "PAUSADO"}, status=status.HTTP_200_OK)


class FinalizarRecorridoAPIView(APIView):
    """
    POST /api/recorrido/finalizar/
    Finaliza el recorrido del ciclista registrando la fecha/hora de fin.
    Verifica si se encuentra dentro del radio de tolerancia de 20 metros respecto a la Meta Oficial.
    Payload: { "recorrido_id": 102, "latitud": -31.468, "longitud": -64.355, "forzar": false }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        recorrido_id = request.data.get('recorrido_id')
        latitud = request.data.get('latitud')
        longitud = request.data.get('longitud')
        forzar = request.data.get('forzar', False)

        if not recorrido_id:
            return Response({"error": "Debe especificar recorrido_id"}, status=status.HTTP_400_BAD_REQUEST)

        recorrido = get_object_or_404(
            RecorridoCiclista.objects.select_related('circuito'),
            id=recorrido_id,
            ciclista=request.user
        )

        # Validación de Meta (Llegada) con radio oficial de 20 metros
        punto_meta = recorrido.circuito.punto_meta if recorrido.circuito else None
        radio_meta = 20
        distancia_a_meta = None
        en_meta = True

        if punto_meta and latitud is not None and longitud is not None:
            distancia_a_meta = calcular_distancia_metros(latitud, longitud, punto_meta[0], punto_meta[1])
            if distancia_a_meta > radio_meta:
                en_meta = False
                if not forzar:
                    return Response(
                        {
                            "fuera_de_meta": True,
                            "error": (
                                f"Te encuentras a {int(distancia_a_meta)} metros de la Meta Oficial. "
                                f"La tolerancia para cerrar carrera es de {radio_meta} metros."
                            ),
                            "distancia_metros": round(distancia_a_meta, 1),
                            "radio_permitido": radio_meta,
                            "punto_meta": {
                                "lat": punto_meta[0],
                                "lng": punto_meta[1]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

        recorrido.estado = 'FINALIZADO'
        recorrido.fin = timezone.now()
        recorrido.save()

        return Response(
            {
                "status": "ok",
                "estado": "FINALIZADO",
                "fin": recorrido.fin,
                "en_meta_oficial": en_meta,
                "distancia_meta_metros": round(distancia_a_meta, 1) if distancia_a_meta is not None else None
            },
            status=status.HTTP_200_OK
        )


class BatchGPSAPIView(APIView):
    """
    POST /api/gps/batch/
    Endpoint clave de telemetría masiva por lotes (Batching cada 30-60 segundos).
    Inserta puntos en bloque con bulk_create y evalúa paradas en comercios sin saturar cPanel.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BatchGPSInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        recorrido_id = serializer.validated_data['recorrido_id']
        puntos_data = serializer.validated_data['puntos']

        recorrido = get_object_or_404(
            RecorridoCiclista.objects.select_related('circuito'),
            id=recorrido_id,
            ciclista=request.user
        )

        if recorrido.estado == 'FINALIZADO':
            return Response(
                {"error": "El recorrido ya ha sido finalizado. No se aceptan más coordenadas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Comercios del circuito para detección de paradas
        comercios = list(recorrido.circuito.comercios.all())

        paradas_detectadas = []
        paradas_ids_vistas = set()
        objetos_gps = []

        for p in puntos_data:
            lat = p['lat']
            lng = p['lng']
            ts = p['timestamp']

            # Preparar objeto para inserción masiva
            objetos_gps.append(
                RegistroGPS(
                    recorrido=recorrido,
                    latitud=lat,
                    longitud=lng,
                    timestamp=ts
                )
            )

            # Verificar si pasa cerca de algún comercio
            parada = evaluar_parada_comercio(lat, lng, comercios)
            if parada and parada['id'] not in paradas_ids_vistas:
                paradas_ids_vistas.add(parada['id'])
                paradas_detectadas.append(parada)

        # Inserción masiva ultra rápida (1 sola query SQL)
        RegistroGPS.objects.bulk_create(objetos_gps)

        # Distancia del lote actual
        distancia_lote = calcular_distancia_total_puntos(
            [{'lat': p['lat'], 'lng': p['lng']} for p in puntos_data]
        )

        return Response(
            {
                "status": "ok",
                "recorrido_id": recorrido.id,
                "puntos_guardados": len(objetos_gps),
                "distancia_lote_metros": round(distancia_lote, 1),
                "paradas_detectadas": paradas_detectadas
            },
            status=status.HTTP_200_OK
        )


class MonitoreoVivoAPIView(APIView):
    """
    GET /api/panel/monitoreo-vivo/
    Devuelve los ciclistas activos con su última posición GPS reportada.
    Utilizado por el dashboard de administración.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        hace_15_minutos = timezone.now() - timedelta(minutes=15)

        recorridos_activos = RecorridoCiclista.objects.filter(
            estado='EN_CURSO'
        ).select_related('ciclista', 'circuito')

        resultado = []
        for r in recorridos_activos:
            ultimo_punto = r.puntos.order_by('-timestamp').first()
            if ultimo_punto:
                activo_reciente = ultimo_punto.timestamp >= hace_15_minutos
                resultado.append({
                    'recorrido_id': r.id,
                    'ciclista_id': r.ciclista.id,
                    'nombre_ciclista': r.ciclista.get_full_name() or r.ciclista.username,
                    'circuito_nombre': r.circuito.nombre,
                    'estado': r.estado,
                    'latitud': ultimo_punto.latitud,
                    'longitud': ultimo_punto.longitud,
                    'ultimo_timestamp': ultimo_punto.timestamp,
                    'activo_reciente': activo_reciente
                })

        return Response(resultado, status=status.HTTP_200_OK)


class NoticiaListAPIView(APIView):
    """
    GET /api/noticias/
    Listado público de noticias ordenadas cronológicamente.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        noticias = Noticia.objects.all()[:10]
        serializer = NoticiaSerializer(noticias, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
