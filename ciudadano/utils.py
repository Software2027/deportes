"""
Funciones auxiliares y algoritmos geoespaciales para el Sistema de Ciclismo.
Cálculos basados en trigonometría esférica (Haversine) en Python puro.
"""

import math
import os
import re
import unicodedata
from typing import List, Dict, Any, Optional
from decimal import Decimal


def calcular_distancia_metros(lat1: float | Decimal, lon1: float | Decimal,
                              lat2: float | Decimal, lon2: float | Decimal) -> float:
    """
    Calcula la distancia ortodrómica en metros entre dos coordenadas geográficas
    utilizando la fórmula de Haversine.

    Parámetros:
        lat1, lon1: Latitud y longitud del punto de origen (grados decimales).
        lat2, lon2: Latitud y longitud del punto de destino (grados decimales).

    Retorna:
        Distancia en metros (float).
    """
    R = 6371000.0  # Radio medio de la Tierra en metros

    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2.0) ** 2)

    # Limitar por posibles imprecisiones de coma flotante
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def calcular_distancia_total_puntos(puntos: List[Dict[str, Any]]) -> float:
    """
    Calcula la distancia acumulada en metros a lo largo de una secuencia ordenada de puntos.
    Cada punto debe ser un diccionario con claves 'lat' (o 'latitud') y 'lng' (o 'longitud').
    """
    if len(puntos) < 2:
        return 0.0

    distancia_acumulada = 0.0
    for i in range(len(puntos) - 1):
        p1 = puntos[i]
        p2 = puntos[i + 1]

        lat1 = p1.get('lat', p1.get('latitud'))
        lon1 = p1.get('lng', p1.get('longitud'))
        lat2 = p2.get('lat', p2.get('latitud'))
        lon2 = p2.get('lng', p2.get('longitud'))

        if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
            distancia_acumulada += calcular_distancia_metros(lat1, lon1, lat2, lon2)

    return distancia_acumulada


def evaluar_parada_comercio(lat: float | Decimal, lon: float | Decimal, comercios) -> Optional[Dict[str, Any]]:
    """
    Verifica si una coordenada GPS se encuentra dentro del radio de tolerancia de algún comercio adherido.
    Asegura un radio mínimo efectivo de 20 metros para compensar el margen del GPS móvil.

    Parámetros:
        lat, lon: Coordenadas capturadas del ciclista.
        comercios: QuerySet o lista de objetos ComercioAdherido.

    Retorna:
        Diccionario con datos del comercio si está en radio, o None si no coincide.
    """
    for comercio in comercios:
        distancia = calcular_distancia_metros(lat, lon, comercio.latitud, comercio.longitud)
        # Radio mínimo de 20 metros garantizado
        radio_efectivo = max(20, getattr(comercio, 'radio_tolerancia_metros', 20) or 20)
        if distancia <= radio_efectivo:
            return {
                'id': comercio.id,
                'nombre': comercio.nombre,
                'categoria': comercio.get_categoria_display() if hasattr(comercio, 'get_categoria_display') else comercio.categoria,
                'distancia_metros': round(distancia, 1),
                'radio_tolerancia': radio_efectivo,
                'imagen_url': comercio.imagen.url if (comercio.imagen and hasattr(comercio.imagen, 'url')) else None
            }
    return None


def calcular_velocidad_kmh(distancia_metros: float, tiempo_segundos: float) -> float:
    """
    Calcula la velocidad en km/h a partir de metros y segundos transcurridos.
    """
    if tiempo_segundos <= 0:
        return 0.0
    metros_por_segundo = distancia_metros / tiempo_segundos
    return round(metros_por_segundo * 3.6, 2)


def normalizar_nombre_archivo(filename: str) -> str:
    """
    Normaliza el nombre de un archivo para almacenamiento seguro:
    - Todo en minúsculas.
    - Espacios reemplazados por guión bajo '_'.
    - Sin caracteres especiales ni acentos/tildes.
    - Mantiene la extensión en minúsculas.
    """
    nombre_base, ext = os.path.splitext(filename)
    # Quitar acentos / tildes
    nombre_sin_tildes = unicodedata.normalize('NFKD', nombre_base).encode('ASCII', 'ignore').decode('utf-8')
    # Convertir a minúsculas
    nombre_lower = nombre_sin_tildes.lower()
    # Reemplazar espacios y guiones múltiples por guión bajo
    nombre_con_guiones = re.sub(r'[\s\-]+', '_', nombre_lower)
    # Conservar solo caracteres alfanuméricos y guión bajo
    nombre_limpio = re.sub(r'[^a-z0-9_]', '', nombre_con_guiones)
    # Eliminar guiones bajos repetidos o en los extremos
    nombre_limpio = re.sub(r'_+', '_', nombre_limpio).strip('_')
    if not nombre_limpio:
        nombre_limpio = 'comercio'
    ext_limpia = ext.lower()
    return f"{nombre_limpio}{ext_limpia}"
