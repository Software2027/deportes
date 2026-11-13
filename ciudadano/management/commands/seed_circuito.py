from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ciudadano.models import (
    CircuitoGeneral,
    SubCircuito,
    PuntosTramo,
    ComercioAdherido,
    RecorridoCiclista,
    RegistroGPS,
    Noticia
)
from django.utils import timezone
from decimal import Decimal


class Command(BaseCommand):
    help = "Carga datos iniciales del circuito oficial de Malagueño, subcircuitos y comercios adheridos."

    def handle(self, *args, **options):
        # 1. Circuito General Activo
        circuito, created = CircuitoGeneral.objects.get_or_create(
            nombre="Reto Urbano Malagueño 2026",
            defaults={
                'descripcion': 'Circuito oficial municipal por el casco urbano, canteras y circuito serrano de Malagueño.',
                'activo': True,
            }
        )
        if not circuito.activo:
            circuito.activo = True
            circuito.save()
        self.stdout.write(self.style.SUCCESS(f"Circuito activo: {circuito.nombre}"))

        # 2. Subcircuitos
        sub1, _ = SubCircuito.objects.get_or_create(
            circuito_general=circuito,
            nombre="Circuito Histórico y Casco Céntrico",
            defaults={'orden': 1, 'color_capa': '#10b981'}
        )
        sub2, _ = SubCircuito.objects.get_or_create(
            circuito_general=circuito,
            nombre="Ruta de las Canteras y Ciclovía",
            defaults={'orden': 2, 'color_capa': '#f59e0b'}
        )
        sub3, _ = SubCircuito.objects.get_or_create(
            circuito_general=circuito,
            nombre="Desafío de las Sierras Chicas",
            defaults={'orden': 3, 'color_capa': '#3b82f6'}
        )

        # 3. Puntos de tramo para cada Subcircuito (Trazado Oficial de Malagueño)
        # Etapa 1: Casco Céntrico e Histórico (Verde #10b981)
        puntos_sub1 = [
            (-31.464500, -64.362000),
            (-31.466000, -64.359000),
            (-31.468500, -64.355000),
            (-31.470200, -64.353500),
            (-31.472000, -64.352000),
        ]
        if not PuntosTramo.objects.filter(subcircuito=sub1).exists():
            for i, (lat, lng) in enumerate(puntos_sub1, 1):
                PuntosTramo.objects.create(
                    subcircuito=sub1,
                    orden=i,
                    latitud=Decimal(str(lat)),
                    longitud=Decimal(str(lng))
                )

        # Etapa 2: Ruta de las Canteras y Ciclovía (Ámbar #f59e0b)
        puntos_sub2 = [
            (-31.472000, -64.352000),
            (-31.474000, -64.350000),
            (-31.476500, -64.346500),
            (-31.479000, -64.343000),
            (-31.482000, -64.340000),
        ]
        if not PuntosTramo.objects.filter(subcircuito=sub2).exists():
            for i, (lat, lng) in enumerate(puntos_sub2, 1):
                PuntosTramo.objects.create(
                    subcircuito=sub2,
                    orden=i,
                    latitud=Decimal(str(lat)),
                    longitud=Decimal(str(lng))
                )

        # Etapa 3: Desafío de las Sierras Chicas (Azul #3b82f6)
        puntos_sub3 = [
            (-31.482000, -64.340000),
            (-31.484500, -64.337000),
            (-31.481500, -64.334000),
            (-31.478000, -64.339000),
            (-31.476000, -64.348000),
        ]
        if not PuntosTramo.objects.filter(subcircuito=sub3).exists():
            for i, (lat, lng) in enumerate(puntos_sub3, 1):
                PuntosTramo.objects.create(
                    subcircuito=sub3,
                    orden=i,
                    latitud=Decimal(str(lat)),
                    longitud=Decimal(str(lng))
                )

        # 4. Comercios y Puntos de Control Adheridos
        comercios_data = [
            ("Punto de Control: Plaza San Martín", "Punto de Control", "Av. San Martín y Belgrano, Malagueño", -31.464500, -64.362000, 35, sub1, "Punto de sellado y largada oficial."),
            ("Puesto de Hidratación Estación Ferrocarril", "Punto de Hidratación", "Predio Ferrocarril, Malagueño", -31.468500, -64.355000, 30, sub1, "Agua mineralizada, sales isotónicas y asistencia básica."),
            ("Bicicletería Malagueño Bike Pro", "Taller de Bicicletas", "Calle Mendoza 320, Malagueño", -31.470200, -64.353500, 25, sub2, "Infladores de alta presión, parches y calibración de cambios."),
            ("Parador Serrano El Mirador", "Restauración", "Ruta Provincial S-271 km 4, Malagueño", -31.474000, -64.350000, 30, sub2, "15% de descuento en colaciones y bebidas con dorsal oficial."),
            ("Centro Polideportivo Municipal Malagueño", "Punto de Control", "Calle Eva Perón s/n, Malagueño", -31.476000, -64.348000, 40, sub3, "Arribo final, premiación y sanitarios."),
        ]
        for nombre, cat, dire, lat, lng, rad, sub, desc in comercios_data:
            ComercioAdherido.objects.get_or_create(
                circuito_general=circuito,
                nombre=nombre,
                defaults={
                    'categoria': cat,
                    'direccion': dire,
                    'latitud': Decimal(str(lat)),
                    'longitud': Decimal(str(lng)),
                    'radio_tolerancia_metros': rad,
                    'subcircuito': sub,
                    'estado': 'Activo',
                    'telefono': '+54 351 498-1234',
                    'descripcion': desc,
                }
            )

        # 5. Noticias de prueba si no existen
        if Noticia.objects.count() == 0:
            Noticia.objects.create(
                titulo="Cómo prepararte para el Gran Reto Malagueño 2026",
                contenido="Consejos de nutrición, chequeo de cubiertas, hidratación y rutas de entrenamiento previo para la gran cita deportiva del municipio.",
                categoria="Eventos",
                autor_nombre="Dirección de Deportes",
                estado="Publicado",
                fecha_publicacion=timezone.now()
            )
            Noticia.objects.create(
                titulo="Los comercios de la ciudad ofrecen descuentos especiales a ciclistas",
                contenido="Presentando tu número de dorsal en locales adheridos de Malagueño accedes a hidratación gratuita, chequeo mecánico y beneficios exclusivos.",
                categoria="Comunidad",
                autor_nombre="Prensa Municipal",
                estado="Publicado",
                fecha_publicacion=timezone.now()
            )
            Noticia.objects.create(
                titulo="Operativo de Seguridad y Tránsito por el Reto Urbano",
                contenido="Defensa Civil y Tránsito Municipal coordinarán cortes preventivos en las canteras y avenidas céntricas para garantizar la seguridad ciclista.",
                categoria="Seguridad",
                autor_nombre="Defensa Civil Malagueño",
                estado="Publicado",
                fecha_publicacion=timezone.now()
            )

        # 6. Ciclistas de prueba para validar en el panel
        from ciudadano.models import Ciclista
        if Ciclista.objects.count() == 0:
            Ciclista.objects.get_or_create(
                dni="38456123",
                defaults={
                    'nombre': "Juan Pablo Rodríguez",
                    'email': "juanpablo.ciclo@gmail.com",
                    'club_entidad': "Malagueño MTB Team",
                    'nivel': "Pro",
                    'estado': "Pendiente",
                    'telefono': "+54 351 689-1122",
                    'contacto_emergencia': "Laura Rodríguez (Madre) - 351-4567890",
                    'observaciones': "Ficha médica presentada. A la espera de validación de dorsal.",
                }
            )
            Ciclista.objects.get_or_create(
                dni="40123987",
                defaults={
                    'nombre': "María Sol Beltrán",
                    'email': "sol.beltran@ciclismomza.com",
                    'club_entidad': "Independiente",
                    'nivel': "Aficionado",
                    'estado': "Validado",
                    'telefono': "+54 351 765-4321",
                    'contacto_emergencia': "Carlos Beltrán (Hermano) - 351-9876543",
                    'observaciones': "Participante admitido oficialmente.",
                }
            )

        self.stdout.write(self.style.SUCCESS("Datos de prueba de Malagueño cargados correctamente en MySQL."))
