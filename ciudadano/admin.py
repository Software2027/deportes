"""
Configuración del panel de administración Django para los modelos del Sistema de Ciclismo.
"""

from django.contrib import admin
from .models import (
    CircuitoGeneral,
    SubCircuito,
    PuntosTramo,
    CategoriaComercio,
    ComercioAdherido,
    RecorridoCiclista,
    RegistroGPS,
    Noticia,
    Ciclista
)

# Personalización institucional del encabezado de Django Admin
admin.site.site_header = "Ciclismo Malagueño — Administración Central"
admin.site.site_title = "Admin Ciclismo Malagueño"
admin.site.index_title = "Panel de Superusuario y Configuración del Sistema"


class SubCircuitoInline(admin.TabularInline):
    model = SubCircuito
    extra = 1
    fields = ('nombre', 'orden', 'color_capa')


class ComercioAdheridoInline(admin.TabularInline):
    model = ComercioAdherido
    extra = 1
    fields = ('nombre', 'categoria', 'latitud', 'longitud', 'radio_tolerancia_metros')


@admin.register(CircuitoGeneral)
class CircuitoGeneralAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'total_subcircuitos', 'total_comercios')
    list_filter = ('activo',)
    search_fields = ('nombre', 'descripcion')
    inlines = [SubCircuitoInline, ComercioAdheridoInline]

    def total_subcircuitos(self, obj):
        return obj.subcircuitos.count()
    total_subcircuitos.short_description = "Subcircuitos"

    def total_comercios(self, obj):
        return obj.comercios.count()
    total_comercios.short_description = "Comercios"


class PuntosTramoInline(admin.TabularInline):
    model = PuntosTramo
    extra = 3
    fields = ('orden', 'latitud', 'longitud')


@admin.register(SubCircuito)
class SubCircuitoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'circuito_general', 'orden', 'color_capa', 'total_puntos')
    list_filter = ('circuito_general',)
    search_fields = ('nombre', 'circuito_general__nombre')
    inlines = [PuntosTramoInline]

    def total_puntos(self, obj):
        return obj.trazado.count()
    total_puntos.short_description = "Puntos de Trazado"


@admin.register(PuntosTramo)
class PuntosTramoAdmin(admin.ModelAdmin):
    list_display = ('subcircuito', 'orden', 'latitud', 'longitud')
    list_filter = ('subcircuito__circuito_general', 'subcircuito')
    search_fields = ('subcircuito__nombre',)


@admin.register(ComercioAdherido)
class ComercioAdheridoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'circuito_general', 'radio_tolerancia_metros', 'latitud', 'longitud')
    list_filter = ('categoria', 'circuito_general')
    search_fields = ('nombre', 'circuito_general__nombre')


class RegistroGPSInline(admin.TabularInline):
    model = RegistroGPS
    extra = 0
    readonly_fields = ('latitud', 'longitud', 'timestamp')
    can_delete = False


@admin.register(RecorridoCiclista)
class RecorridoCiclistaAdmin(admin.ModelAdmin):
    list_display = ('id', 'ciclista', 'circuito', 'estado', 'inicio', 'fin', 'total_puntos_gps')
    list_filter = ('estado', 'circuito', 'inicio')
    search_fields = ('ciclista__username', 'ciclista__email')
    readonly_fields = ('inicio',)
    inlines = [RegistroGPSInline]

    def total_puntos_gps(self, obj):
        return obj.puntos.count()
    total_puntos_gps.short_description = "Puntos GPS"


@admin.register(RegistroGPS)
class RegistroGPSAdmin(admin.ModelAdmin):
    list_display = ('id', 'recorrido', 'latitud', 'longitud', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('recorrido__ciclista__username',)


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'fecha_publicacion', 'tiene_imagen')
    search_fields = ('titulo', 'contenido')
    list_filter = ('fecha_publicacion',)

    def tiene_imagen(self, obj):
        return bool(obj.imagen)
    tiene_imagen.boolean = True
    tiene_imagen.short_description = "¿Tiene Imagen?"


@admin.register(CategoriaComercio)
class CategoriaComercioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'total_comercios', 'descripcion')
    search_fields = ('nombre', 'descripcion')

    def total_comercios(self, obj):
        return ComercioAdherido.objects.filter(categoria__iexact=obj.nombre).count()
    total_comercios.short_description = "Comercios Asociados"


@admin.register(Ciclista)
class CiclistaAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_id',
        'nombre',
        'dni',
        'edad_display',
        'email',
        'nivel',
        'estado',
        'clave_asignada_display',
        'fecha_registro'
    )
    list_filter = ('estado', 'nivel', 'fecha_registro')
    search_fields = ('nombre', 'dni', 'email', 'club_entidad')
    readonly_fields = ('codigo_id', 'fecha_registro')
    fieldsets = (
        ('Identificación y Cuenta', {
            'fields': ('codigo_id', 'user', 'nombre', 'dni', 'fecha_nacimiento', 'email')
        }),
        ('Credencial de Acceso (Solo Administrador)', {
            'fields': ('clave_asignada',),
            'description': 'Contraseña asignada al participante. En la base de datos de usuarios está cifrada con hash seguro PBKDF2; aquí se conserva legible solo para el superusuario/administrador en caso de soporte u olvido.'
        }),
        ('Acreditación y Estado', {
            'fields': ('club_entidad', 'nivel', 'estado', 'foto', 'observaciones')
        }),
        ('Contacto de Seguridad', {
            'fields': ('telefono', 'contacto_emergencia', 'fecha_registro')
        }),
    )

    def clave_asignada_display(self, obj):
        return obj.clave_asignada if obj.clave_asignada else "—"
    clave_asignada_display.short_description = "Clave (Admin)"

    def edad_display(self, obj):
        return f"{obj.edad} años" if obj.edad is not None else "—"
    edad_display.short_description = "Edad"
