"""
Serializadores de Django REST Framework para el Sistema de Ciclismo.
Permite la serialización de geometrías de circuitos, comercios, y la deserialización de lotes GPS.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    CircuitoGeneral,
    SubCircuito,
    PuntosTramo,
    ComercioAdherido,
    RecorridoCiclista,
    RegistroGPS,
    Noticia
)


# ==============================================================================
# 1. SERIALIZADORES DE CIRCUITOS Y GEOMETRÍAS
# ==============================================================================

class PuntosTramoSerializer(serializers.ModelSerializer):
    """Serializa un vértice individual de la polilínea del subcircuito."""
    class Meta:
        model = PuntosTramo
        fields = ['orden', 'latitud', 'longitud']


class SubCircuitoSerializer(serializers.ModelSerializer):
    """Serializa un subcircuito con toda su secuencia ordenada de puntos de trazado y su longitud calculada."""
    trazado = PuntosTramoSerializer(many=True, read_only=True)
    distancia_km = serializers.FloatField(read_only=True)
    distancia_metros = serializers.FloatField(read_only=True)

    class Meta:
        model = SubCircuito
        fields = ['id', 'nombre', 'orden', 'color_capa', 'distancia_km', 'distancia_metros', 'trazado']


class ComercioAdheridoSerializer(serializers.ModelSerializer):
    """Serializa los comercios y puntos de control adheridos al circuito."""
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)

    class Meta:
        model = ComercioAdherido
        fields = [
            'id',
            'nombre',
            'categoria',
            'categoria_display',
            'latitud',
            'longitud',
            'radio_tolerancia_metros',
            'imagen'
        ]


class CircuitoGeneralSerializer(serializers.ModelSerializer):
    """
    Serializa el circuito general completo con sus subcircuitos/tramos y comercios.
    Utilizado por el motor Leaflet en el portal público y en la app ciclista.
    """
    subcircuitos = SubCircuitoSerializer(many=True, read_only=True)
    comercios = ComercioAdheridoSerializer(many=True, read_only=True)
    movilidades_lista = serializers.ListField(read_only=True)

    class Meta:
        model = CircuitoGeneral
        fields = [
            'id', 'nombre', 'descripcion', 'activo', 'distancia_total_km',
            'movilidades_permitidas', 'movilidades_lista', 'subcircuitos', 'comercios'
        ]


# ==============================================================================
# 2. SERIALIZADORES DE TELEMETRÍA GPS Y BATCHING
# ==============================================================================

class PuntoGPSInputSerializer(serializers.Serializer):
    """Valida cada una de las coordenadas enviadas dentro del paquete por lote."""
    lat = serializers.DecimalField(max_digits=10, decimal_places=6, required=False)
    lng = serializers.DecimalField(max_digits=10, decimal_places=6, required=False)
    latitud = serializers.DecimalField(max_digits=10, decimal_places=6, required=False)
    longitud = serializers.DecimalField(max_digits=10, decimal_places=6, required=False)
    timestamp = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        lat = attrs.get('lat') if attrs.get('lat') is not None else attrs.get('latitud')
        lng = attrs.get('lng') if attrs.get('lng') is not None else attrs.get('longitud')
        if lat is None or lng is None:
            raise serializers.ValidationError("Debe proporcionar las coordenadas (lat/lng o latitud/longitud).")
        attrs['lat'] = lat
        attrs['lng'] = lng
        if not attrs.get('timestamp'):
            from django.utils import timezone
            attrs['timestamp'] = timezone.now()
        return attrs


class BatchGPSInputSerializer(serializers.Serializer):
    """
    Valida el paquete JSON de lote (batching) emitido periódicamente por el frontend.
    Formato compatible:
    {
        "recorrido_id": 102,
        "puntos": [
            {"lat": -34.603722, "lng": -58.381592, "timestamp": "2026-10-19T10:00:00Z"},
            ...
        ]
    }
    """
    recorrido_id = serializers.IntegerField()
    puntos = PuntoGPSInputSerializer(many=True, allow_empty=True)


class RegistroGPSSerializer(serializers.ModelSerializer):
    """Serializador para lectura de registros GPS ya persistidos."""
    class Meta:
        model = RegistroGPS
        fields = ['id', 'latitud', 'longitud', 'timestamp']


class RecorridoCiclistaSerializer(serializers.ModelSerializer):
    """Serializa la sesión de carrera con estado y cantidad de puntos registrados."""
    ciclista_nombre = serializers.CharField(source='ciclista.get_full_name', read_only=True)
    ciclista_username = serializers.CharField(source='ciclista.username', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    total_puntos = serializers.IntegerField(source='puntos.count', read_only=True)

    class Meta:
        model = RecorridoCiclista
        fields = [
            'id',
            'ciclista',
            'ciclista_username',
            'ciclista_nombre',
            'circuito',
            'inicio',
            'fin',
            'estado',
            'estado_display',
            'modalidad',
            'tipo_movilidad',
            'total_puntos'
        ]


# ==============================================================================
# 3. SERIALIZADOR DE NOTICIAS
# ==============================================================================

class NoticiaSerializer(serializers.ModelSerializer):
    """Serializa novedades y alertas meteorológicas/viales."""
    autor_display = serializers.CharField(read_only=True)

    class Meta:
        model = Noticia
        fields = ['id', 'titulo', 'contenido', 'imagen', 'fecha_publicacion', 'categoria', 'autor_display', 'estado', 'vistas']
