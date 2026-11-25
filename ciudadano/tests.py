"""
Pruebas unitarias y de integración para modelos, utilidades geoespaciales y APIs REST.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from django.utils import timezone
from .models import (
    CircuitoGeneral,
    SubCircuito,
    PuntosTramo,
    ComercioAdherido,
    RecorridoCiclista,
    RegistroGPS,
    Noticia,
    Ciclista
)
from .utils import (
    calcular_distancia_metros,
    calcular_distancia_total_puntos,
    evaluar_parada_comercio,
    calcular_velocidad_kmh
)


class GeoUtilsTestCase(TestCase):
    """Pruebas de funciones matemáticas geoespaciales y algoritmos."""

    def test_haversine_distancia_cero(self):
        """La distancia entre un punto y sí mismo debe ser 0 metros."""
        lat = -34.603722
        lon = -58.381592
        distancia = calcular_distancia_metros(lat, lon, lat, lon)
        self.assertAlmostEqual(distancia, 0.0, places=1)

    def test_haversine_distancia_conocida(self):
        """
        Distancia entre el Obelisco (-34.603722, -58.381592) y Plaza de Mayo (-34.608333, -58.371389).
        La distancia aproximada en línea recta es de ~1080 - 1100 metros.
        """
        lat1, lon1 = -34.603722, -58.381592
        lat2, lon2 = -34.608333, -58.371389
        distancia = calcular_distancia_metros(lat1, lon1, lat2, lon2)
        self.assertTrue(1050 < distancia < 1150, f"Distancia calculada: {distancia}m fuera de rango esperado.")

    def test_calcular_distancia_total_puntos(self):
        puntos = [
            {'lat': -34.603722, 'lng': -58.381592},
            {'lat': -34.608333, 'lng': -58.371389},
        ]
        total = calcular_distancia_total_puntos(puntos)
        self.assertTrue(total > 1000)

    def test_calcular_velocidad_kmh(self):
        # 1000 metros en 120 segundos (2 minutos) => 30 km/h
        velocidad = calcular_velocidad_kmh(1000, 120)
        self.assertEqual(velocidad, 30.0)


class ModelosTestCase(TestCase):
    """Pruebas de creación e integridad de los modelos del sistema."""

    def setUp(self):
        self.user = User.objects.create_user(username='ciclista_test', password='password123')
        self.circuito = CircuitoGeneral.objects.create(
            nombre="Circuito Costero 2026",
            descripcion="Circuito de prueba",
            activo=True
        )
        self.subcircuito = SubCircuito.objects.create(
            circuito_general=self.circuito,
            nombre="Etapa 1: Tramo Norte",
            orden=1,
            color_capa="#00FF00"
        )
        self.comercio = ComercioAdherido.objects.create(
            circuito_general=self.circuito,
            nombre="Puesto Hidratación Central",
            categoria="HIDRATACION",
            latitud=Decimal("-34.603722"),
            longitud=Decimal("-58.381592"),
            radio_tolerancia_metros=50
        )

    def test_creacion_circuito_y_subcircuito(self):
        self.assertEqual(self.circuito.nombre, "Circuito Costero 2026")
        self.assertTrue(self.circuito.activo)
        self.assertEqual(self.subcircuito.orden, 1)
        self.assertEqual(str(self.circuito), "Circuito Costero 2026 (ACTIVO)")

    def test_creacion_puntos_tramo(self):
        punto = PuntosTramo.objects.create(
            subcircuito=self.subcircuito,
            orden=1,
            latitud=Decimal("-34.603722"),
            longitud=Decimal("-58.381592")
        )
        self.assertEqual(self.subcircuito.trazado.count(), 1)
        self.assertEqual(punto.latitud, Decimal("-34.603722"))

    def test_evaluar_parada_comercio_dentro_del_radio(self):
        # Punto a 15 metros del comercio
        lat_ciclista = -34.603800
        lon_ciclista = -58.381600
        comercios = ComercioAdherido.objects.filter(circuito_general=self.circuito)
        parada = evaluar_parada_comercio(lat_ciclista, lon_ciclista, comercios)
        self.assertIsNotNone(parada)
        self.assertEqual(parada['id'], self.comercio.id)
        self.assertEqual(parada['nombre'], "Puesto Hidratación Central")

    def test_evaluar_parada_comercio_fuera_del_radio(self):
        # Punto a más de 500 metros
        lat_ciclista = -34.610000
        lon_ciclista = -58.390000
        comercios = ComercioAdherido.objects.filter(circuito_general=self.circuito)
        parada = evaluar_parada_comercio(lat_ciclista, lon_ciclista, comercios)
        self.assertIsNone(parada)

    def test_recorrido_y_registro_gps(self):
        recorrido = RecorridoCiclista.objects.create(
            ciclista=self.user,
            circuito=self.circuito,
            estado='EN_CURSO'
        )
        RegistroGPS.objects.create(
            recorrido=recorrido,
            latitud=Decimal("-34.603722"),
            longitud=Decimal("-58.381592"),
            timestamp=timezone.now()
        )
        self.assertEqual(recorrido.puntos.count(), 1)
        self.assertEqual(recorrido.estado, 'EN_CURSO')

    def test_creacion_noticia(self):
        noticia = Noticia.objects.create(
            titulo="Alerta de Viento Fuerte",
            contenido="Se recomienda circular con precaución en la zona costera."
        )
        self.assertEqual(noticia.titulo, "Alerta de Viento Fuerte")
        self.assertEqual(str(noticia), "Alerta de Viento Fuerte")


class APIRestTestCase(TestCase):
    """Pruebas de endpoints REST, batching GPS y ciclo de vida de carrera."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='ciclista_api', password='password123')
        self.client.force_authenticate(user=self.user)

        self.circuito = CircuitoGeneral.objects.create(
            nombre="Circuito Principal Nocturno",
            activo=True
        )
        self.subcircuito = SubCircuito.objects.create(
            circuito_general=self.circuito,
            nombre="Etapa 1",
            orden=1,
            color_capa="#FF0000"
        )
        PuntosTramo.objects.create(
            subcircuito=self.subcircuito,
            orden=1,
            latitud=Decimal("-34.603722"),
            longitud=Decimal("-58.381592")
        )
        PuntosTramo.objects.create(
            subcircuito=self.subcircuito,
            orden=2,
            latitud=Decimal("-34.604500"),
            longitud=Decimal("-58.382000")
        )

        self.comercio = ComercioAdherido.objects.create(
            circuito_general=self.circuito,
            nombre="Taller El Rayo",
            categoria="TALLER",
            latitud=Decimal("-34.603750"),
            longitud=Decimal("-58.381600"),
            radio_tolerancia_metros=35
        )

    def test_get_circuito_activo(self):
        response = self.client.get('/api/circuitos/activo/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre'], "Circuito Principal Nocturno")
        self.assertEqual(len(response.data['subcircuitos']), 1)
        self.assertEqual(len(response.data['subcircuitos'][0]['trazado']), 2)
        self.assertEqual(len(response.data['comercios']), 1)

    def test_ciclo_completo_recorrido_y_batch_gps(self):
        # 1. Iniciar recorrido
        res_inicio = self.client.post('/api/recorrido/iniciar/', {}, format='json')
        self.assertIn(res_inicio.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        recorrido_id = res_inicio.data['recorrido']['id']
        self.assertEqual(res_inicio.data['recorrido']['estado'], 'EN_CURSO')

        # 2. Enviar lote de telemetría GPS (Batching)
        # Punto 1 está a ~5 metros del comercio "Taller El Rayo"
        # Punto 2 y 3 avanzan por la ruta
        payload_lote = {
            "recorrido_id": recorrido_id,
            "puntos": [
                {
                    "lat": "-34.603752",
                    "lng": "-58.381602",
                    "timestamp": "2026-10-20T10:00:00Z"
                },
                {
                    "lat": "-34.604000",
                    "lng": "-58.381700",
                    "timestamp": "2026-10-20T10:00:10Z"
                },
                {
                    "lat": "-34.604200",
                    "lng": "-58.381800",
                    "timestamp": "2026-10-20T10:00:20Z"
                }
            ]
        }
        res_batch = self.client.post('/api/gps/batch/', payload_lote, format='json')
        self.assertEqual(res_batch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_batch.data['puntos_guardados'], 3)
        self.assertTrue(len(res_batch.data['paradas_detectadas']) >= 1)
        self.assertEqual(res_batch.data['paradas_detectadas'][0]['id'], self.comercio.id)

        # Verificar persistencia en base de datos
        recorrido = RecorridoCiclista.objects.get(id=recorrido_id)
        self.assertEqual(recorrido.puntos.count(), 3)

        # 3. Pausar recorrido
        res_pausa = self.client.post('/api/recorrido/pausar/', {"recorrido_id": recorrido_id}, format='json')
        self.assertEqual(res_pausa.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pausa.data['estado'], 'PAUSADO')

        # 4. Finalizar recorrido
        res_fin = self.client.post('/api/recorrido/finalizar/', {"recorrido_id": recorrido_id}, format='json')
        self.assertEqual(res_fin.status_code, status.HTTP_200_OK)
        self.assertEqual(res_fin.data['estado'], 'FINALIZADO')

        # 5. Intentar enviar puntos a un recorrido FINALIZADO debe fallar con 400
        res_fallo = self.client.post('/api/gps/batch/', payload_lote, format='json')
        self.assertEqual(res_fallo.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_gps_con_claves_latitud_longitud(self):
        """Valida que el batch acepte indistintamente claves latitud/longitud o lat/lng."""
        res_inicio = self.client.post('/api/recorrido/iniciar/', {}, format='json')
        recorrido_id = res_inicio.data['recorrido']['id']
        payload_lote = {
            "recorrido_id": recorrido_id,
            "puntos": [
                {
                    "latitud": "-31.468000",
                    "longitud": "-64.355000",
                    "timestamp": "2026-11-12T12:00:00Z"
                }
            ]
        }
        res_batch = self.client.post('/api/gps/batch/', payload_lote, format='json')
        self.assertEqual(res_batch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_batch.data['puntos_guardados'], 1)

    def test_api_noticias(self):
        Noticia.objects.create(titulo="Noticia Test", contenido="Contenido Test")
        response = self.client.get('/api/noticias/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['titulo'], "Noticia Test")


class PublicViewsTestCase(TestCase):
    """Pruebas para las vistas públicas y renderizado de plantillas."""

    def setUp(self):
        self.circuito = CircuitoGeneral.objects.create(
            nombre="Circuito Costero 2026",
            descripcion="Circuito de prueba ciudadana",
            activo=True
        )
        self.noticia = Noticia.objects.create(
            titulo="Gran Apertura del Circuito",
            contenido="Este fin de semana se inaugura el circuito oficial con presencia municipal."
        )

    def test_landing_page_render(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/index.html')
        self.assertContains(response, "Malagueño")
        self.assertContains(response, "Circuito Costero 2026")
        self.assertContains(response, "Gran Apertura del Circuito")

    def test_noticia_detalle_render(self):
        response = self.client.get(f'/noticia/{self.noticia.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/noticia_detalle.html')
        self.assertContains(response, "Gran Apertura del Circuito")

    def test_noticias_listado_ciudadano(self):
        """Verifica que el listado de noticias público cargue las noticias y responda 200."""
        response = self.client.get('/noticias/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/noticias_listado.html')
        self.assertContains(response, "Novedades del Circuito")
        self.assertContains(response, "Gran Apertura del Circuito")

    def test_contacto_view_get_and_post(self):
        """Verifica la inscripción oficial de un ciclista con foto carnet, estado Pendiente y validación de duplicados."""
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        import io
        import os

        # GET
        res_get = self.client.get('/contacto/')
        self.assertEqual(res_get.status_code, 200)
        self.assertTemplateUsed(res_get, 'ciudadano/contacto.html')
        self.assertContains(res_get, "Asistencia Municipal")
        self.assertContains(res_get, "Ficha de Inscripción")

        # Simular foto carnet con nombre no normalizado
        img_io = io.BytesIO()
        image = Image.new('RGB', (100, 100), color='green')
        image.save(img_io, format='JPEG')
        img_io.seek(0)
        foto_carnet = SimpleUploadedFile("Mi Foto Carnet (2026).JPG", img_io.read(), content_type="image/jpeg")

        # POST: Envío de ficha de ciclista con foto carnet
        data = {
            'nombre': 'Martín Ciclista',
            'dni': '38123456',
            'email': 'martin@ciclismo.com',
            'telefono': '3514980000',
            'fecha_nacimiento': '1995-05-15',
            'club_entidad': 'Club Ciclista Malagueño',
            'nivel': 'Pro',
            'contacto_emergencia': 'Laura - 3519876543',
            'observaciones': 'Sin alergias conocidas.',
            'foto': foto_carnet
        }
        res_post = self.client.post('/contacto/', data, follow=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertContains(res_post, "Inscripción registrada con éxito")
        self.assertContains(res_post, "PENDIENTE")

        # Verificar que el Ciclista se guardó en BD con estado Pendiente y foto normalizada
        ciclista = Ciclista.objects.filter(dni='38123456').first()
        self.assertIsNotNone(ciclista)
        self.assertEqual(ciclista.nombre, 'Martín Ciclista')
        self.assertEqual(ciclista.estado, 'Pendiente')
        self.assertEqual(ciclista.nivel, 'Pro')
        self.assertTrue(bool(ciclista.foto))
        self.assertIn('ciclistas/mi_foto_carnet_2026', ciclista.foto.name.lower())
        self.assertTrue(os.path.isfile(ciclista.foto.path))

        # Intento con DNI duplicado: debe rechazar
        data_dni_dup = data.copy()
        data_dni_dup['email'] = 'otro_email@test.com'
        res_dni_dup = self.client.post('/contacto/', data_dni_dup, follow=True)
        self.assertEqual(res_dni_dup.status_code, 200)
        self.assertContains(res_dni_dup, "ya se encuentra registrado en el padrón")

        # Intento con Email duplicado: debe rechazar
        data_email_dup = data.copy()
        data_email_dup['dni'] = '99999999'
        res_email_dup = self.client.post('/contacto/', data_email_dup, follow=True)
        self.assertEqual(res_email_dup.status_code, 200)
        self.assertContains(res_email_dup, "ya se encuentra registrado en el sistema")

        # Limpiar foto física creada en test
        if os.path.isfile(ciclista.foto.path):
            os.remove(ciclista.foto.path)

    def test_header_boton_ingresar(self):
        """Verifica que el header contenga el botón 'Ingresar' que dirija a /login/."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresar")
        self.assertContains(response, 'href="/login/"')

    def test_login_page_render_get(self):
        """Verifica que el login renderice correctamente con todos sus elementos y el Pop Up de recuperación."""
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/login.html')
        self.assertContains(response, "Bienvenido")
        self.assertContains(response, "DNI o Correo Electrónico")
        self.assertContains(response, "Contraseña")
        self.assertContains(response, "Ingresar")
        self.assertContains(response, "Registrarme en el evento")
        self.assertContains(response, "¿Olvidaste tu contraseña?")
        self.assertContains(response, "modalRecuperarPassword")
        self.assertContains(response, "ciclismo@malagueno.gob.ar")
        self.assertContains(response, "Nombre y Apellido")
        self.assertContains(response, "Edad")
        self.assertContains(response, "DNI")

    def test_ruta_inscripcion_alias(self):
        """Verifica que /inscripcion/ responda 200 con el formulario de inscripción."""
        res = self.client.get('/inscripcion/')
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'ciudadano/contacto.html')

    def test_login_post_pase_directo(self):
        """Verifica el flujo de autenticación real: validado (por Gmail o DNI), pendiente y contraseña errónea."""
        # 1. Crear ciclista validado con su usuario Django
        user_validado = User.objects.create_user(
            username='40123456',
            email='mateo.ciclista@gmail.com',
            password='password123',
            first_name='Mateo'
        )
        Ciclista.objects.create(
            user=user_validado,
            nombre='Mateo Carrera',
            dni='40123456',
            email='mateo.ciclista@gmail.com',
            estado='Validado'
        )

        # 2. Login exitoso con Gmail
        res_email = self.client.post('/login/', {
            'username': 'mateo.ciclista@gmail.com',
            'password': 'password123'
        }, follow=False)
        self.assertEqual(res_email.status_code, 302)
        self.assertIn('/mi-progreso/', res_email['Location'])

        # 3. Login exitoso con DNI
        self.client.logout()
        res_dni = self.client.post('/login/', {
            'username': '40123456',
            'password': 'password123'
        }, follow=False)
        self.assertEqual(res_dni.status_code, 302)
        self.assertIn('/mi-progreso/', res_dni['Location'])

        # 4. Login rechazado con contraseña incorrecta
        self.client.logout()
        res_pass_err = self.client.post('/login/', {
            'username': '40123456',
            'password': 'clave_incorrecta'
        }, follow=True)
        self.assertEqual(res_pass_err.status_code, 200)
        self.assertContains(res_pass_err, "Contraseña incorrecta")

        # 5. Ciclista en estado Pendiente no puede ingresar
        Ciclista.objects.create(
            nombre='Aspirante Pendiente',
            dni='50123456',
            email='aspirante@gmail.com',
            estado='Pendiente'
        )
        res_pend = self.client.post('/login/', {
            'username': 'aspirante@gmail.com',
            'password': 'cualquier_clave'
        }, follow=True)
        self.assertEqual(res_pend.status_code, 200)
        self.assertContains(res_pend, "PENDIENTE")

    def test_mi_progreso_render_autenticado(self):
        """Verifica que un ciclista autenticado pueda ver su panel con KPIs y subcircuitos."""
        user = User.objects.create_user(
            username='ciclista_panel',
            email='panel@malagueno.gob.ar',
            password='password123',
            first_name='Mateo'
        )
        self.client.force_login(user)

        response = self.client.get('/mi-progreso/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/mi_progreso.html')
        self.assertContains(response, "Mateo")
        self.assertContains(response, "Mis Sub-circuitos")
        self.assertContains(response, "Cronograma de Paradas")
        self.assertContains(response, "Distancia")
        self.assertContains(response, "Cantidad de tramos")

    def test_inscribir_circuito_activo(self):
        """Verifica la acción de inscripción rápida al circuito activo desde el panel."""
        user = User.objects.create_user(
            username='ciclista_inscripto',
            email='inscripcion@malagueno.gob.ar',
            password='password123'
        )
        self.client.force_login(user)

        res_post = self.client.post('/mi-progreso/', {'accion': 'inscribir'}, follow=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertContains(res_post, "Circuito sumado con éxito")
        self.assertTrue(RecorridoCiclista.objects.filter(ciclista=user, circuito=self.circuito).exists())

    def test_mapa_carrera_render(self):
        """Verifica que la pantalla fullscreen de carrera renderice con sus componentes."""
        user = User.objects.create_user(
            username='ciclista_carrera',
            email='carrera@malagueno.gob.ar',
            password='password123'
        )
        self.client.force_login(user)

        response = self.client.get('/mapa-carrera/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/mapa_carrera.html')
        self.assertContains(response, "mapa-carrera-fs")
        self.assertContains(response, "hud-velocidad")
        self.assertContains(response, "hud-distancia")
        self.assertContains(response, "hud-tiempo")
        self.assertContains(response, "INICIAR RECORRIDO")

    def test_noticias_listado_sin_vistas(self):
        """El listado de noticias no debe mostrar el contador de vistas/lecturas."""
        noticia = Noticia.objects.create(
            titulo="Nueva ciclovía en Malagueño",
            contenido="Se habilitaron 5 nuevos kilómetros de ciclovía protegida.",
            categoria="Urbanismo",
            estado="Publicado",
            vistas=150
        )
        response = self.client.get('/noticias/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/noticias_listado.html')
        self.assertContains(response, "Nueva ciclovía en Malagueño")
        # Verificar que no figure el texto de lecturas
        self.assertNotContains(response, "150 lecturas")
        self.assertNotContains(response, "news-read-views")

    def test_noticia_detalle_hero_oscuro_sin_vistas(self):
        """El detalle de noticia debe tener hero oscuro con título y descripción, sin contador de lecturas."""
        noticia = Noticia.objects.create(
            titulo="Incremento del 20% en el uso de bicicletas",
            contenido="El observatorio de movilidad urbana registró un aumento significativo en traslados sustentables diarios.",
            categoria="Comunidad",
            estado="Publicado",
            vistas=355
        )
        response = self.client.get(f'/noticia/{noticia.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/noticia_detalle.html')
        self.assertContains(response, "article-hero-section")
        self.assertContains(response, "article-hero-overlay")
        self.assertContains(response, "Incremento del 20% en el uso de bicicletas")
        self.assertContains(response, "El observatorio de movilidad urbana registró un aumento significativo")
        # Asegurar que no se muestre el texto de lecturas ni vistas
        self.assertNotContains(response, "355 lecturas")
        self.assertNotContains(response, "news-read-views")

    def test_comercios_listado_render(self):
        """Verifica que el listado público de comercios renderice correctamente con filtros y datos."""
        comercio = ComercioAdherido.objects.create(
            nombre="Café del Ciclista Malagueño",
            direccion="Av. San Martín 123",
            categoria="Restauración",
            estado="Activo",
            latitud=Decimal("-31.464500"),
            longitud=Decimal("-64.362000"),
            telefono="351 1234567",
            descripcion="Descuentos del 15% para ciclistas acreditados."
        )
        response = self.client.get('/comercios/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/comercios_listado.html')
        self.assertContains(response, "Red Comercial de Malagueño")
        self.assertContains(response, "Café del Ciclista Malagueño")
        self.assertContains(response, "Av. San Martín 123")
        self.assertContains(response, "Ver detalles y mapa")

    def test_comercio_detalle_render_con_google_maps(self):
        """Verifica que la vista detalle de un comercio muestre la ficha técnica y el mapa de Google Maps."""
        comercio = ComercioAdherido.objects.create(
            nombre="Taller Pro Malagueño",
            direccion="Belgrano 450",
            categoria="Taller de Bicicletas",
            estado="Activo",
            latitud=Decimal("-31.465000"),
            longitud=Decimal("-64.363000"),
            telefono="351 9876543",
            descripcion="Mecánica ligera gratuita en carrera."
        )
        response = self.client.get(f'/comercio/{comercio.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ciudadano/comercio_detalle.html')
        self.assertContains(response, "Taller Pro Malagueño")
        self.assertContains(response, "Belgrano 450")
        self.assertContains(response, "Localización en Google Maps")
        self.assertContains(response, "Cómo llegar en Google Maps")
        self.assertContains(response, "maps.google.com/maps?q=-31.465000,-64.363000")


class RecorridoLargadaYParadaTestCase(TestCase):
    """Pruebas de validación del punto de largada y registro de paradas/detenciones."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='ciclista_largada', password='password123')
        self.client.force_authenticate(user=self.user)

        self.circuito = CircuitoGeneral.objects.create(
            nombre="Gran Reto Sierras 2026",
            descripcion="Circuito oficial con largada y paradas",
            activo=True,
            radio_largada_metros=80
        )
        self.etapa = SubCircuito.objects.create(
            circuito_general=self.circuito,
            nombre="Etapa 1: Casco Urbano",
            orden=1
        )
        # Punto de largada Km 0
        PuntosTramo.objects.create(
            subcircuito=self.etapa,
            orden=1,
            latitud=Decimal("-31.468000"),
            longitud=Decimal("-64.355000")
        )
        # Comercio adherido del circuito
        self.comercio = ComercioAdherido.objects.create(
            circuito_general=self.circuito,
            nombre="Bar Identidad",
            categoria="Punto de Hidratación",
            latitud=Decimal("-31.470000"),
            longitud=Decimal("-64.355000"),
            radio_tolerancia_metros=40
        )

    def test_iniciar_recorrido_fuera_de_radio_largada(self):
        """Si el ciclista intenta iniciar lejos del Km 0, debe retornar 400 y fuera_de_radio=True."""
        response = self.client.post(
            '/api/recorrido/iniciar/',
            {
                'circuito_id': self.circuito.id,
                'latitud': -31.485000,
                'longitud': -64.355000
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data.get('fuera_de_radio'))
        self.assertIn('distancia_metros', response.data)
        self.assertTrue(response.data['distancia_metros'] > 80)

    def test_iniciar_recorrido_dentro_de_radio_largada(self):
        """Si el ciclista está a menos de 80m del Km 0, el recorrido inicia con éxito."""
        response = self.client.post(
            '/api/recorrido/iniciar/',
            {
                'circuito_id': self.circuito.id,
                'latitud': -31.468010,
                'longitud': -64.355010
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['recorrido']['estado'], 'EN_CURSO')
        self.assertIn('recorrido', response.data)

    def test_registrar_parada_en_comercio(self):
        """Al presionar Detener dentro del radio de un comercio, se registra la visita oficial."""
        recorrido = RecorridoCiclista.objects.create(
            ciclista=self.user,
            circuito=self.circuito,
            estado='EN_CURSO'
        )
        # Detenerse exactamente al lado del comercio (-31.470005, -64.355005)
        response = self.client.post(
            '/api/recorrido/detener/',
            {
                'recorrido_id': recorrido.id,
                'latitud': -31.470005,
                'longitud': -64.355005
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['es_comercio_adherido'])
        self.assertEqual(response.data['nombre_parada'], "Bar Identidad")
        self.assertEqual(response.data['estado'], "PAUSADO")

        recorrido.refresh_from_db()
        self.assertEqual(recorrido.estado, 'PAUSADO')
        self.assertEqual(recorrido.paradas_registradas.count(), 1)
        parada = recorrido.paradas_registradas.first()
        self.assertEqual(parada.comercio, self.comercio)
        self.assertTrue(parada.es_comercio_adherido)

    def test_registrar_parada_tecnica_descanso(self):
        """Al presionar Detener fuera de comercios, se registra como parada técnica / descanso."""
        recorrido = RecorridoCiclista.objects.create(
            ciclista=self.user,
            circuito=self.circuito,
            estado='EN_CURSO'
        )
        response = self.client.post(
            '/api/recorrido/detener/',
            {
                'recorrido_id': recorrido.id,
                'latitud': -31.475000,
                'longitud': -64.355000
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['es_comercio_adherido'])
        self.assertEqual(response.data['nombre_parada'], "Parada Técnica / Descanso")
        self.assertEqual(response.data['estado'], "PAUSADO")

    def test_admin_acceso_mi_progreso_aislamiento(self):
        """Un usuario con sesión administrativa que intenta ir a /mi-progreso/ es redirigido con mensaje informativo."""
        admin_user = User.objects.create_superuser(
            username='admin_aislamiento',
            email='admin.aisla@malagueno.gob.ar',
            password='password123'
        )
        self.client.force_login(admin_user)
        session = self.client.session
        session['tipo_sesion'] = 'administrador'
        session.save()

        response = self.client.get('/mi-progreso/?circuito_id=2', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/dashboard.html')
        self.assertContains(response, "Has ingresado con tu cuenta administrativa del municipio")

    def test_template_error_500_render(self):
        """La vista de prueba de error 500 y el template institucional funcionan correctamente."""
        response = self.client.get('/error/500/')
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "CÓDIGO 500", status_code=500)
        self.assertContains(response, "Ocurrió un inconveniente temporal", status_code=500)




