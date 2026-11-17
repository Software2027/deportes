"""
Modelos de Datos para el Sistema de Ciclismo Municipal.
Incluye entidades de circuitos, tramos, comercios adheridos, recorridos y telemetría GPS.
Diseñado para alta eficiencia sin dependencias de GeoDjango/GDAL.
"""

import os
from django.db import models
from django.contrib.auth.models import User
from .utils import normalizar_nombre_archivo


def ruta_logo_comercio(instance, filename):
    """
    Genera la ruta de almacenamiento para el logo del comercio:
    media/comercios/<nombre_normalizado>
    """
    nombre_normalizado = normalizar_nombre_archivo(filename)
    return os.path.join('comercios', nombre_normalizado)


def ruta_foto_ciclista(instance, filename):
    """
    Genera la ruta de almacenamiento para la foto carnet del ciclista:
    media/ciclistas/<nombre_normalizado>
    """
    nombre_normalizado = normalizar_nombre_archivo(filename)
    return os.path.join('ciclistas', nombre_normalizado)


# ==============================================================================
# 1. CIRCUITO GENERAL Y SUBCIRCUITOS
# ==============================================================================

class CircuitoGeneral(models.Model):
    """
    Representa el evento o circuito maestro de la ciudad (ej: 'Circuito Costanera 2026').
    """
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Circuito")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activo = models.BooleanField(
        default=False,
        verbose_name="Activo",
        help_text="Define qué circuito se muestra por defecto en el portal público y en la app ciclista."
    )
    fecha_evento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha del Evento Oficial",
        help_text="Fecha programada para la largada de la competencia oficial."
    )
    fecha_limite_inscripcion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Límite de Inscripción",
        help_text="Fecha hasta la cual los ciclistas pueden postularse para la carrera oficial."
    )
    radio_largada_metros = models.IntegerField(
        default=20,
        verbose_name="Radio de Largada (metros)",
        help_text="Distancia máxima de tolerancia (20 m recomendados) respecto al Km 0 para validar la largada oficial."
    )

    class Meta:
        verbose_name = "Circuito General"
        verbose_name_plural = "Circuitos Generales"
        ordering = ['-activo', 'nombre']

    def __str__(self):
        return f"{self.nombre} {'(ACTIVO)' if self.activo else ''}"

    @property
    def es_evento(self):
        """Indica si el circuito corresponde a una carrera o evento oficial con fecha programada."""
        return self.fecha_evento is not None

    @property
    def evento_vigente(self):
        """Indica si la fecha de la carrera es igual o posterior a la jornada actual."""
        if not self.fecha_evento:
            return False
        from datetime import date
        return self.fecha_evento >= date.today()

    @property
    def inscripciones_abiertas(self):
        """Indica si el período de inscripción a la carrera oficial está activo según la fecha límite configurada."""
        if not self.fecha_evento:
            return False
        from datetime import date
        today = date.today()
        # Si tiene fecha límite de inscripción explícita, se respeta estrictamente
        if self.fecha_limite_inscripcion:
            return today <= self.fecha_limite_inscripcion
        # Si no se configuró fecha límite, cierra el mismo día del evento oficial
        return today <= self.fecha_evento

    @property
    def evento_concluido(self):
        """Indica si la fecha programada de la carrera ya transcurrió pero el circuito continúa disponible para uso libre."""
        if not self.fecha_evento:
            return False
        from datetime import date
        return self.fecha_evento < date.today()

    @property
    def punto_largada(self):
        """Retorna (latitud, longitud) del punto de inicio de la primera etapa."""
        primer_sub = self.subcircuitos.order_by('orden').first()
        if primer_sub:
            primer_pto = primer_sub.trazado.order_by('orden').first()
            if primer_pto:
                return float(primer_pto.latitud), float(primer_pto.longitud)
        return None

    @property
    def punto_meta(self):
        """Retorna (latitud, longitud) del punto de llegada o fin de la última etapa."""
        ultimo_sub = self.subcircuitos.order_by('-orden').first()
        if ultimo_sub:
            ultimo_pto = ultimo_sub.trazado.order_by('-orden').first()
            if ultimo_pto:
                return float(ultimo_pto.latitud), float(ultimo_pto.longitud)
        return None

    @property
    def distancia_total_km(self):
        """Calcula la distancia total acumulada del circuito sumando los trazados de sus etapas."""
        total_metros = sum(sub.distancia_metros for sub in self.subcircuitos.all())
        return round(total_metros / 1000.0, 2)

    @property
    def inscripcion_abierta(self):
        """Indica si el período de inscripción para el evento oficial sigue vigente."""
        if not self.evento_vigente:
            return False
        if not self.fecha_limite_inscripcion:
            return True
        from datetime import date
        return date.today() <= self.fecha_limite_inscripcion


class SubCircuito(models.Model):
    """
    Subdivisiones o etapas que componen un circuito general (ej: 'Etapa 1: Tramo Norte').
    """
    circuito_general = models.ForeignKey(
        CircuitoGeneral,
        related_name='subcircuitos',
        on_delete=models.CASCADE,
        verbose_name="Circuito General"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Etapa / Subcircuito")
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden de Secuencia")
    color_capa = models.CharField(
        max_length=7,
        default='#FF0000',
        verbose_name="Color de Capa (HEX)",
        help_text="Código hexadecimal (ej. #FF5733) para dibujar la línea en Leaflet."
    )

    class Meta:
        verbose_name = "Subcircuito / Etapa"
        verbose_name_plural = "Subcircuitos / Etapas"
        ordering = ['orden']

    def __str__(self):
        return f"[{self.orden}] {self.nombre} - {self.circuito_general.nombre}"

    @property
    def distancia_metros(self):
        """Calcula la distancia geodésica acumulada de los puntos del tramo utilizando la fórmula de Haversine."""
        from .utils import calcular_distancia_total_puntos
        pts = list(self.trazado.values('latitud', 'longitud').order_by('orden'))
        if not pts or len(pts) < 2:
            return 0.0
        return calcular_distancia_total_puntos(pts)

    @property
    def distancia_km(self):
        """Devuelve la distancia del tramo o etapa en kilómetros redondeada a 2 decimales."""
        m = self.distancia_metros
        return round(m / 1000.0, 2)


class PuntosTramo(models.Model):
    """
    Secuencia ordenada de coordenadas geográficas que dibujan la polilínea del subcircuito.
    """
    subcircuito = models.ForeignKey(
        SubCircuito,
        related_name='trazado',
        on_delete=models.CASCADE,
        verbose_name="Subcircuito"
    )
    orden = models.PositiveIntegerField(verbose_name="Orden del Punto")
    latitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitud")
    longitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitud")

    class Meta:
        verbose_name = "Punto de Tramo"
        verbose_name_plural = "Puntos de Tramo"
        ordering = ['orden']
        indexes = [
            models.Index(fields=['subcircuito', 'orden']),
        ]

    def __str__(self):
        return f"{self.subcircuito.nombre} - P{self.orden} ({self.latitud}, {self.longitud})"


# ==============================================================================
# 2. COMERCIOS Y PUNTOS ADHERIDOS
# ==============================================================================

class CategoriaComercio(models.Model):
    """
    Categorías administrables para los comercios y puntos adheridos.
    Gestionables por el superusuario desde /admin.
    """
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Nombre de la Categoría")
    descripcion = models.TextField(blank=True, verbose_name="Descripción / Beneficios para Ciclistas")

    class Meta:
        verbose_name = "Categoría de Comercio"
        verbose_name_plural = "Categorías de Comercios"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class ComercioAdherido(models.Model):
    """
    Establecimientos y paradas de asistencia adheridas al circuito (talleres, hidratación, gastronomía).
    """
    CATEGORIAS = [
        ('Restauración', 'Restauración / Gastronomía'),
        ('Taller de Bicicletas', 'Taller de Bicicletas'),
        ('Tienda Deportiva', 'Tienda Deportiva'),
        ('Alojamiento', 'Alojamiento / Hospedaje'),
        ('Punto de Hidratación', 'Punto de Hidratación'),
        ('Punto de Control', 'Punto de Control / Sellado'),
        ('Otro', 'Otro Servicio'),
    ]

    ESTADOS = [
        ('Activo', 'Activo'),
        ('En Revision', 'En Revisión'),
        ('Inactivo', 'Inactivo'),
    ]

    circuito_general = models.ForeignKey(
        CircuitoGeneral,
        related_name='comercios',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Circuito General"
    )
    subcircuito = models.ForeignKey(
        SubCircuito,
        related_name='comercios',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Subcircuito / Etapa Específica",
        help_text="Opcional: Asocia este comercio a una etapa específica del circuito."
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Establecimiento")
    direccion = models.CharField(max_length=200, blank=True, verbose_name="Dirección / Domicilio")
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIAS,
        default='Punto de Hidratación',
        verbose_name="Categoría"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='Activo',
        verbose_name="Estado"
    )
    latitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitud")
    longitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitud")
    radio_tolerancia_metros = models.IntegerField(
        default=20,
        verbose_name="Radio de Tolerancia (metros)",
        help_text="Distancia máxima de tolerancia (20 m por defecto) para validar automáticamente la visita del ciclista."
    )
    imagen = models.ImageField(
        upload_to=ruta_logo_comercio,
        null=True,
        blank=True,
        verbose_name="Imagen / Logo del Comercio"
    )
    telefono = models.CharField(max_length=40, blank=True, verbose_name="Teléfono")
    descripcion = models.TextField(blank=True, verbose_name="Descripción / Beneficios para Ciclistas")

    class Meta:
        verbose_name = "Comercio / Punto Adherido"
        verbose_name_plural = "Comercios y Puntos Adheridos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"

    def save(self, *args, **kwargs):
        """
        Al actualizar o reemplazar la imagen, elimina la anterior físicamente de media/comercios.
        """
        if self.pk:
            try:
                antiguo = ComercioAdherido.objects.get(pk=self.pk)
                if antiguo.imagen and antiguo.imagen != self.imagen:
                    if os.path.isfile(antiguo.imagen.path):
                        os.remove(antiguo.imagen.path)
            except ComercioAdherido.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Al eliminar el comercio, elimina físicamente su imagen de media/comercios.
        """
        if self.imagen:
            try:
                if os.path.isfile(self.imagen.path):
                    os.remove(self.imagen.path)
            except Exception:
                pass
        super().delete(*args, **kwargs)



# ==============================================================================
# 3. RECORRIDOS Y REGISTROS GPS DEL CICLISTA
# ==============================================================================

class RecorridoCiclista(models.Model):
    """
    Sesión de actividad o carrera de un ciclista registrado sobre un circuito general.
    """
    ESTADOS = [
        ('LISTO', 'Inscripto / Listo para Iniciar'),
        ('EN_CURSO', 'En Curso'),
        ('PAUSADO', 'Pausado'),
        ('FINALIZADO', 'Finalizado'),
    ]
    MODALIDADES = [
        ('OFICIAL', 'Evento Oficial'),
        ('LIBRE', 'Libre / Práctica'),
    ]

    ciclista = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recorridos',
        verbose_name="Ciclista"
    )
    circuito = models.ForeignKey(
        CircuitoGeneral,
        on_delete=models.CASCADE,
        related_name='recorridos_realizados',
        verbose_name="Circuito"
    )
    inicio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora de Inicio")
    fin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha y Hora de Finalización")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='LISTO',
        verbose_name="Estado del Recorrido"
    )
    modalidad = models.CharField(
        max_length=20,
        choices=MODALIDADES,
        default='LIBRE',
        verbose_name="Modalidad del Recorrido"
    )

    class Meta:
        verbose_name = "Recorrido de Ciclista"
        verbose_name_plural = "Recorridos de Ciclistas"
        ordering = ['-inicio']

    def __str__(self):
        return f"Recorrido #{self.id} ({self.get_modalidad_display()}) - {self.ciclista.username} [{self.get_estado_display()}]"

    @property
    def distancia_km(self):
        """Calcula la distancia acumulada en kilómetros sumando la telemetría GPS registrada."""
        from .utils import calcular_distancia_total_puntos
        pts = list(self.puntos.values('latitud', 'longitud').order_by('timestamp'))
        if not pts:
            return 0.0
        return round(calcular_distancia_total_puntos(pts) / 1000.0, 2)


class ParadaRecorrido(models.Model):
    """
    Detención puntual registrada cuando el participante presiona 'Detener'.
    Identifica si frenó en un comercio adherido, punto de hidratación o descanso técnico.
    """
    recorrido = models.ForeignKey(
        RecorridoCiclista,
        related_name='paradas_registradas',
        on_delete=models.CASCADE,
        verbose_name="Recorrido"
    )
    comercio = models.ForeignKey(
        ComercioAdherido,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visitas_ciclistas',
        verbose_name="Comercio / Punto de Hidratación"
    )
    latitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitud de Detención")
    longitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitud de Detención")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Hora de Detención")
    es_comercio_adherido = models.BooleanField(default=False, verbose_name="¿Es Comercio / Punto Adherido?")
    nombre_parada = models.CharField(max_length=150, blank=True, verbose_name="Nombre de la Parada o Comercio")

    class Meta:
        verbose_name = "Parada de Recorrido"
        verbose_name_plural = "Paradas de Recorridos"
        ordering = ['-timestamp']

    def __str__(self):
        tipo = f"Punto Oficial: {self.nombre_parada}" if self.es_comercio_adherido else "Parada Técnica"
        return f"{tipo} (R#{self.recorrido_id}) - {self.timestamp.strftime('%H:%M:%S')}"


class RegistroGPS(models.Model):
    """
    Puntos individuales de telemetría GPS transmitidos por el dispositivo del ciclista.
    """
    recorrido = models.ForeignKey(
        RecorridoCiclista,
        related_name='puntos',
        on_delete=models.CASCADE,
        verbose_name="Recorrido"
    )
    latitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitud")
    longitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitud")
    timestamp = models.DateTimeField(verbose_name="Marca Temporal")

    class Meta:
        verbose_name = "Registro GPS"
        verbose_name_plural = "Registros GPS"
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['recorrido', 'timestamp']),
        ]

    def __str__(self):
        return f"GPS #{self.id} (R#{self.recorrido_id}): {self.latitud}, {self.longitud}"


# ==============================================================================
# 4. CONTENIDO Y COMUNICADOS (NOTICIAS)
# ==============================================================================

class Noticia(models.Model):
    """
    Publicaciones informativas, avisos de seguridad y novedades del evento.
    """
    CATEGORIAS = [
        ('Urbanismo', 'Urbanismo'),
        ('Seguridad', 'Seguridad'),
        ('Comunidad', 'Comunidad'),
        ('Eventos', 'Eventos'),
        ('Oficial', 'Oficial'),
    ]

    ESTADOS = [
        ('Publicado', 'Publicado'),
        ('Borrador', 'Borrador'),
        ('Archivado', 'Archivado'),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Título")
    contenido = models.TextField(verbose_name="Contenido")
    imagen = models.ImageField(
        upload_to='noticias/',
        null=True,
        blank=True,
        verbose_name="Imagen Destacada"
    )
    categoria = models.CharField(
        max_length=60,
        choices=CATEGORIAS,
        default='Comunidad',
        verbose_name="Categoría"
    )
    autor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='noticias',
        verbose_name="Usuario Autor"
    )
    autor_nombre = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name="Nombre de Autor"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='Publicado',
        verbose_name="Estado de Publicación"
    )
    vistas = models.PositiveIntegerField(
        default=0,
        verbose_name="Lecturas / Visitas"
    )
    fecha_publicacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Publicación")

    class Meta:
        verbose_name = "Noticia / Comunicado"
        verbose_name_plural = "Noticias y Comunicados"
        ordering = ['-fecha_publicacion']

    def __str__(self):
        return self.titulo

    @property
    def autor_display(self):
        """Retorna el nombre público del autor de la noticia."""
        if self.autor_nombre and self.autor_nombre.strip():
            return self.autor_nombre.strip()
        if self.autor:
            nombre = self.autor.get_full_name()
            if nombre and nombre.strip():
                return nombre.strip()
            return self.autor.username
        return "Admin Ciclo"

    @property
    def estado_badge_class(self):
        """Retorna la clase CSS para el badge según su estado."""
        mapa = {
            'Publicado': 'badge-publicado',
            'Borrador': 'badge-borrador',
            'Archivado': 'badge-archivado',
        }
        return mapa.get(self.estado, 'badge-publicado')


# ==============================================================================
# 5. GESTIÓN DE CICLISTAS Y PARTICIPANTES
# ==============================================================================

class Ciclista(models.Model):
    """
    Participante acreditado en la plataforma de ciclismo municipal.
    """
    NIVELES = [
        ('Aficionado', 'Aficionado'),
        ('Pro', 'Pro'),
        ('Elite', 'Elite'),
    ]
    ESTADOS = [
        ('Pendiente', 'Pendiente'),
        ('Validado', 'Validado'),
        ('Rechazado', 'Rechazado'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfil_ciclista',
        verbose_name="Usuario de Sistema"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre y Apellido")
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    dni = models.CharField(max_length=25, unique=True, verbose_name="DNI / Documento")
    club_entidad = models.CharField(max_length=120, default="Independiente", verbose_name="Club / Entidad")
    nivel = models.CharField(max_length=20, choices=NIVELES, default='Aficionado', verbose_name="Nivel")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pendiente', verbose_name="Estado de Validación")
    telefono = models.CharField(max_length=40, blank=True, verbose_name="Teléfono")
    contacto_emergencia = models.CharField(max_length=150, blank=True, verbose_name="Contacto de Emergencia")
    foto = models.ImageField(
        upload_to=ruta_foto_ciclista,
        null=True,
        blank=True,
        verbose_name="Foto Carnet / Perfil"
    )
    clave_asignada = models.CharField(
        max_length=128,
        blank=True,
        default='',
        verbose_name="Clave Asignada (Solo Administrador)",
        help_text="Clave registrada al aprobar la inscripción o generada para soporte al ciclista en caso de olvido."
    )
    fecha_nacimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Nacimiento"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones / Documentación")

    class Meta:
        verbose_name = "Ciclista"
        verbose_name_plural = "Ciclistas"
        ordering = ['id']

    def __str__(self):
        return f"{self.codigo_id} - {self.nombre} ({self.dni})"

    @property
    def codigo_id(self):
        return f"CIC-{self.id:03d}"

    @property
    def nombre_completo(self):
        """Retorna el nombre y apellido del ciclista para compatibilidad."""
        return self.nombre

    @property
    def edad(self):
        """Retorna la edad en años si la fecha de nacimiento está registrada."""
        if not self.fecha_nacimiento:
            return None
        from datetime import date
        hoy = date.today()
        cumplio = (hoy.month, hoy.day) >= (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        return hoy.year - self.fecha_nacimiento.year - (0 if cumplio else 1)

    def save(self, *args, **kwargs):
        """
        Al actualizar o reemplazar la foto carnet, elimina la anterior físicamente de media/ciclistas.
        """
        if self.pk:
            try:
                antiguo = Ciclista.objects.get(pk=self.pk)
                if antiguo.foto and antiguo.foto != self.foto:
                    if os.path.isfile(antiguo.foto.path):
                        os.remove(antiguo.foto.path)
            except Ciclista.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Al eliminar o rechazar al ciclista, elimina físicamente su foto carnet de media/ciclistas y su User si existe.
        """
        if self.foto:
            try:
                if os.path.isfile(self.foto.path):
                    os.remove(self.foto.path)
            except Exception:
                pass
        if self.user:
            try:
                self.user.delete()
            except Exception:
                pass
        super().delete(*args, **kwargs)

