"""
Pruebas unitarias y de integración para el Panel de Administración Municipal.
Verifica login administrativo, redirección al dashboard, autenticación y logout.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from ciudadano.models import CircuitoGeneral, SubCircuito, ComercioAdherido, Noticia


class PanelLoginDashboardTests(TestCase):
    """
    Suite de pruebas para el acceso administrativo interno y vista dashboard.
    """

    def setUp(self):
        self.client = Client()
        # Crear usuario administrador oficial
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@malagueno.gob.ar',
            password='password123',
            first_name='Admin',
            last_name='Municipal'
        )

        # Circuito activo con subcircuitos
        self.circuito = CircuitoGeneral.objects.create(
            nombre="Reto Urbano Malagueño 2026",
            descripcion="Circuito oficial de pruebas",
            activo=True
        )
        self.sub1 = SubCircuito.objects.create(
            circuito_general=self.circuito,
            nombre="Etapa 1: Casco Céntrico",
            orden=1,
            color_capa="#10b981"
        )

    def test_login_admin_page_render(self):
        """La vista /panel/login/ debe responder con status 200 y contener los elementos clave."""
        response = self.client.get(reverse('panel_login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/login.html')
        self.assertContains(response, 'Acceso Interno')
        self.assertContains(response, 'Portal de Gestión Administrativa de la Municipalidad de Malagueño')
        self.assertContains(response, 'Correo Electrónico')
        self.assertContains(response, 'Confirmar')

    def test_login_admin_post_success(self):
        """Al enviar credenciales válidas debe autenticar y redirigir al Dashboard."""
        response = self.client.post(reverse('panel_login'), {
            'email': 'admin@malagueno.gob.ar',
            'password': 'password123'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/dashboard.html')
        self.assertTrue(response.context['user'].is_authenticated)

    def test_login_admin_post_invalid_rejected(self):
        """Sin credenciales o con credenciales incorrectas debe rechazar el acceso y permanecer en login."""
        response = self.client.post(reverse('panel_login'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/login.html')
        self.assertFalse(response.context['user'].is_authenticated)

    def test_admin_django_route_accessible(self):
        """La ruta /admin/ debe estar activa y responder correctamente."""
        response = self.client.get('/admin/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ciclismo Malagueño')

    def test_dashboard_view_content(self):
        """El dashboard debe mostrar el título Panel de Control, KPIs, gráfico semanal y accesos rápidos."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('panel_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/dashboard.html')
        self.assertContains(response, 'Panel de Control')
        self.assertContains(response, 'PARTICIPANTES TOTALES')
        self.assertContains(response, 'CIRCUITOS ACTIVOS')
        self.assertContains(response, 'COMERCIOS ALIADOS')
        self.assertContains(response, 'Participación Semanal')
        self.assertContains(response, 'Actividad Reciente')
        self.assertContains(response, 'Impacto Comercial Local')
        self.assertContains(response, 'Gestión de Usuarios')
        self.assertContains(response, 'Control de Circuitos')
        self.assertContains(response, 'dashboardQuickActions')

    def test_logout_admin(self):
        """El logout debe cerrar sesión y redirigir al login interno."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('panel_logout'))
        self.assertRedirects(response, reverse('panel_login'))

    def test_ciclistas_list_view_render(self):
        """El listado de ciclistas debe responder 200 y contener los elementos de la interfaz."""
        from ciudadano.models import Ciclista
        Ciclista.objects.get_or_create(
            dni='12345678X',
            defaults={
                'nombre': 'Mateo Carrera',
                'email': 'mateo.carrera@example.com',
                'club_entidad': 'Veloz Ciclo Club',
                'nivel': 'Elite',
                'estado': 'Validado'
            }
        )
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('panel_ciclistas_listado'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/gestion_ciclistas/listado_ciclistas.html')
        self.assertContains(response, 'Gestión de Ciclistas')
        self.assertContains(response, 'Listado de Ciclistas')
        self.assertContains(response, 'TOTAL REGISTRADOS')
        self.assertContains(response, 'PENDIENTES VALIDACIÓN')
        self.assertContains(response, 'Mateo Carrera')

    def test_ciclista_create_post(self):
        """Crear un ciclista vía POST debe guardarlo en BD y redirigir al listado."""
        from ciudadano.models import Ciclista
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('panel_ciclistas_nuevo'), {
            'nombre': 'Ciclista Nuevo Test',
            'email': 'nuevo@ciclista.com',
            'dni': '99887766T',
            'telefono': '3514981111',
            'contacto_emergencia': '3514982222',
            'fecha_nacimiento': '1998-04-12',
            'club_entidad': 'Club Malagueño',
            'nivel': 'Pro',
            'estado': 'Validado'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Ciclista.objects.filter(dni='99887766T').exists())

    def test_ciclista_detail_and_edit(self):
        """Ver y editar ciclista existente."""
        from ciudadano.models import Ciclista
        ciclista, _ = Ciclista.objects.get_or_create(
            dni='45678912Z',
            defaults={
                'nombre': 'Carlos Quintana',
                'email': 'carlos.q@test.com',
                'fecha_nacimiento': '1996-03-20',
                'telefono': '3514981111',
                'contacto_emergencia': '3514982222',
                'club_entidad': 'Sierra Central Team',
                'nivel': 'Pro',
                'estado': 'Validado'
            }
        )
        self.client.force_login(self.admin_user)

        # Ver detalle
        res_ver = self.client.get(reverse('panel_ciclista_ver', kwargs={'pk': ciclista.id}))
        self.assertEqual(res_ver.status_code, 200)
        self.assertContains(res_ver, 'Carlos Quintana')

        # Editar
        res_edit = self.client.post(reverse('panel_ciclista_editar', kwargs={'pk': ciclista.id}), {
            'nombre': 'Carlos Quintana Editado',
            'email': 'carlos.q@test.com',
            'dni': '45678912Z',
            'telefono': '3514981111',
            'contacto_emergencia': '3514982222',
            'fecha_nacimiento': '1996-03-20',
            'club_entidad': 'Sierra Central Team',
            'nivel': 'Elite',
            'estado': 'Validado'
        }, follow=True)
        self.assertEqual(res_edit.status_code, 200)
        ciclista.refresh_from_db()
        self.assertEqual(ciclista.nombre, 'Carlos Quintana Editado')
        self.assertEqual(ciclista.nivel, 'Elite')

    def test_ciclista_delete(self):
        """Eliminar ciclista vía POST."""
        from ciudadano.models import Ciclista
        c = Ciclista.objects.create(
            nombre='Para Borrar',
            email='borrar@test.com',
            dni='00000000B'
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('panel_ciclista_eliminar', kwargs={'pk': c.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Ciclista.objects.filter(id=c.id).exists())

    def test_ciclistas_exportar_csv(self):
        """Exportar ciclistas en CSV."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('panel_ciclistas_exportar_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('ciclistas_malagueno.csv', response['Content-Disposition'])

    def test_ciclista_cambiar_estado(self):
        """El administrador puede aprobar asignando clave, o rechazar (eliminando el registro e imagen física)."""
        from ciudadano.models import Ciclista
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        import io
        import os

        # Simular foto carnet
        img_io = io.BytesIO()
        image = Image.new('RGB', (100, 100), color='purple')
        image.save(img_io, format='JPEG')
        img_io.seek(0)
        uploaded = SimpleUploadedFile("Foto Carnet Aspirante (1).JPG", img_io.read(), content_type="image/jpeg")

        c = Ciclista.objects.create(
            nombre='Ciclista Candidato',
            email='candidato@gmail.com',
            dni='77889900X',
            foto=uploaded,
            estado='Pendiente'
        )
        ruta_foto = c.foto.path
        self.assertTrue(os.path.isfile(ruta_foto))
        self.assertIn('ciclistas/foto_carnet_aspirante_1', c.foto.name.lower())

        self.client.force_login(self.admin_user)

        # 1. El admin aprueba / valida la solicitud asignando clave personalizada vía POST
        url_validar = reverse('panel_ciclista_cambiar_estado', kwargs={'pk': c.id, 'nuevo_estado': 'Validado'})
        res_val = self.client.post(url_validar, {'password': 'ClaveSegura2026!'}, follow=True)
        self.assertEqual(res_val.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.estado, 'Validado')
        self.assertIsNotNone(c.user)
        self.assertEqual(c.user.email, 'candidato@gmail.com')
        self.assertTrue(c.user.check_password('ClaveSegura2026!'))
        self.assertEqual(c.clave_asignada, 'ClaveSegura2026!')

        # Verificar que el formulario en modo ver muestre la clave asignada al administrador
        res_ficha = self.client.get(reverse('panel_ciclista_ver', kwargs={'pk': c.id}))
        self.assertEqual(res_ficha.status_code, 200)
        self.assertContains(res_ficha, 'Clave Asignada del Ciclista')
        self.assertContains(res_ficha, 'ClaveSegura2026!')

        # 2. El admin rechaza la solicitud: se debe eliminar el registro e imagen física de media/ciclistas
        url_rechazar = reverse('panel_ciclista_cambiar_estado', kwargs={'pk': c.id, 'nuevo_estado': 'Rechazado'})
        res_rech = self.client.get(url_rechazar, follow=True)
        self.assertEqual(res_rech.status_code, 200)
        self.assertFalse(Ciclista.objects.filter(id=c.id).exists())
        self.assertFalse(os.path.isfile(ruta_foto))

    def test_comercios_list_view_render(self):
        """El listado de comercios debe responder 200 y contener KPIs y comercios adheridos."""
        comercio = ComercioAdherido.objects.create(
            circuito_general=self.circuito,
            nombre="BiciCafé El Retiro Test",
            direccion="Av. San Martín 450, Malagueño, Córdoba",
            categoria="Restauración",
            estado="Activo",
            latitud=-31.4648,
            longitud=-64.3615,
            radio_tolerancia_metros=30
        )
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('panel_comercios_listado'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/gestion_comercios/listado_comercios.html')
        self.assertContains(response, 'Gestión de Comercios')
        self.assertContains(response, 'Listado de Establecimientos')
        self.assertContains(response, 'Total Comercios')
        self.assertContains(response, 'Activos')
        self.assertContains(response, 'BiciCafé El Retiro Test')
        self.assertContains(response, '-31.4648, -64.3615')
        self.assertContains(response, '30m')

    def test_comercio_create_post(self):
        """Crear un comercio vía POST debe guardarlo en BD y redirigir al listado."""
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('panel_comercio_nuevo'), {
            'nombre': 'Taller Nuevo Test',
            'direccion': 'Belgrano 180, Malagueño, Córdoba',
            'categoria': 'Taller de Bicicletas',
            'estado': 'Activo',
            'latitud': '-31.466500',
            'longitud': '-64.363800',
            'radio_tolerancia_metros': '50',
            'telefono': '+549351000111',
            'descripcion': 'Servicios de mecánica integral en Malagueño'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ComercioAdherido.objects.filter(nombre='Taller Nuevo Test').exists())
        nuevo = ComercioAdherido.objects.get(nombre='Taller Nuevo Test')
        self.assertEqual(nuevo.radio_tolerancia_metros, 50)
        self.assertEqual(nuevo.categoria, 'Taller de Bicicletas')

    def test_comercio_detail_and_edit(self):
        """Ver detalle y editar un comercio existente en Malagueño."""
        comercio = ComercioAdherido.objects.create(
            circuito_general=self.circuito,
            nombre="SportVilla Test",
            direccion="Ruta Provincial C45 Km 2, Malagueño, Córdoba",
            categoria="Tienda Deportiva",
            estado="Inactivo",
            latitud=-31.4715,
            longitud=-64.3540,
            radio_tolerancia_metros=100
        )
        self.client.force_login(self.admin_user)

        # Ver detalle (modo ver)
        res_ver = self.client.get(reverse('panel_comercio_ver', kwargs={'pk': comercio.id}))
        self.assertEqual(res_ver.status_code, 200)
        self.assertTemplateUsed(res_ver, 'panel/gestion_comercios/form_comercios.html')
        self.assertContains(res_ver, 'SportVilla Test')

        # Editar comercio
        res_edit = self.client.post(reverse('panel_comercio_editar', kwargs={'pk': comercio.id}), {
            'nombre': 'SportVilla Modificado',
            'direccion': 'Ruta Provincial C45 Km 3, Malagueño, Córdoba',
            'categoria': 'Tienda Deportiva',
            'estado': 'Activo',
            'latitud': '-31.4720',
            'longitud': '-64.3545',
            'radio_tolerancia_metros': '80',
            'telefono': '+54 351 123456',
            'descripcion': 'Descuento 15% para ciclistas de Malagueño'
        }, follow=True)
        self.assertEqual(res_edit.status_code, 200)
        comercio.refresh_from_db()
        self.assertEqual(comercio.nombre, 'SportVilla Modificado')
        self.assertEqual(comercio.estado, 'Activo')
        self.assertEqual(comercio.radio_tolerancia_metros, 80)

    def test_comercio_delete(self):
        """Eliminar un comercio vía POST."""
        comercio = ComercioAdherido.objects.create(
            circuito_general=self.circuito,
            nombre="Comercio a Eliminar",
            latitud=-31.0,
            longitud=-64.0
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('panel_comercio_eliminar', kwargs={'pk': comercio.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ComercioAdherido.objects.filter(id=comercio.id).exists())

    def test_comercio_imagen_normalizacion_y_reemplazo(self):
        """Verifica que el logo del comercio se normalice (minúsculas, sin espacios ni especiales) y que al reemplazar se elimine la anterior."""
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        import io
        import os

        self.client.force_login(self.admin_user)

        # Crear imagen simulada 1
        img_io1 = io.BytesIO()
        image1 = Image.new('RGB', (100, 100), color='green')
        image1.save(img_io1, format='PNG')
        img_io1.seek(0)
        uploaded1 = SimpleUploadedFile("Mi Café & Taller (1).PNG", img_io1.read(), content_type="image/png")

        # 1. Crear comercio con imagen
        res_create = self.client.post(reverse('panel_comercio_nuevo'), {
            'nombre': 'Bici Café Test Logo',
            'direccion': 'Av. Central 100',
            'categoria': 'Restauración',
            'estado': 'Activo',
            'latitud': '-31.464500',
            'longitud': '-64.362000',
            'radio_tolerancia_metros': '30',
            'imagen': uploaded1
        }, follow=True)
        self.assertEqual(res_create.status_code, 200)

        comercio = ComercioAdherido.objects.get(nombre='Bici Café Test Logo')
        self.assertTrue(bool(comercio.imagen))
        # Debe normalizarse: mi_cafe_taller_1.png
        self.assertIn('comercios/mi_cafe_taller_1', comercio.imagen.name.lower())
        self.assertTrue(comercio.imagen.name.endswith('.png'))
        ruta_archivo1 = comercio.imagen.path
        self.assertTrue(os.path.isfile(ruta_archivo1))

        # 2. Reemplazar imagen con nueva imagen
        img_io2 = io.BytesIO()
        image2 = Image.new('RGB', (100, 100), color='blue')
        image2.save(img_io2, format='JPEG')
        img_io2.seek(0)
        uploaded2 = SimpleUploadedFile("Nuevo LOGO Establecimiento #2.JPG", img_io2.read(), content_type="image/jpeg")

        res_edit = self.client.post(reverse('panel_comercio_editar', kwargs={'pk': comercio.id}), {
            'nombre': 'Bici Café Test Logo',
            'direccion': 'Av. Central 100',
            'categoria': 'Restauración',
            'estado': 'Activo',
            'latitud': '-31.464500',
            'longitud': '-64.362000',
            'radio_tolerancia_metros': '30',
            'imagen': uploaded2
        }, follow=True)
        self.assertEqual(res_edit.status_code, 200)

        comercio.refresh_from_db()
        self.assertIn('comercios/nuevo_logo_establecimiento_2', comercio.imagen.name.lower())
        ruta_archivo2 = comercio.imagen.path
        self.assertTrue(os.path.isfile(ruta_archivo2))
        # La imagen anterior debe haber sido eliminada de media/comercios
        self.assertFalse(os.path.isfile(ruta_archivo1))

        # 3. Al eliminar el comercio, su imagen también se borra físicamente
        comercio.delete()
        self.assertFalse(os.path.isfile(ruta_archivo2))

    def test_circuitos_list_view_render(self):
        """El listado de circuitos debe responder 200 y mostrar los circuitos existentes y KPIs."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('panel_circuitos_listado'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/gestion_circuitos/listado_circuitos.html')
        self.assertContains(response, 'Gestión de Circuitos')
        self.assertContains(response, 'Total Circuitos')
        self.assertContains(response, 'Reto Urbano Malagueño 2026')
        self.assertContains(response, 'Etapa 1: Casco Céntrico')

    def test_circuito_editor_view(self):
        """El editor de circuitos debe cargar correctamente en modo nuevo y en modo edición."""
        self.client.force_login(self.admin_user)

        # Modo nuevo
        res_nuevo = self.client.get(reverse('panel_circuito_nuevo'))
        self.assertEqual(res_nuevo.status_code, 200)
        self.assertTemplateUsed(res_nuevo, 'panel/gestion_circuitos/editor_circuito.html')
        self.assertContains(res_nuevo, 'Herramientas del Circuito')

        # Modo edición
        res_edit = self.client.get(reverse('panel_circuito_editar', kwargs={'pk': self.circuito.id}))
        self.assertEqual(res_edit.status_code, 200)
        self.assertContains(res_edit, 'Reto Urbano Malagueño 2026')

    def test_circuito_guardar_api_post(self):
        """La API de guardado debe persistir circuito, etapas/polilíneas y comercios adheridos."""
        import json
        from ciudadano.models import PuntosTramo

        comercio = ComercioAdherido.objects.create(
            nombre="Comercio Para Circuito",
            latitud=-31.4645,
            longitud=-64.3620
        )

        payload = {
            'nombre': 'Circuito Nuevo Test',
            'descripcion': 'Prueba de trazado',
            'activo': True,
            'etapas': [
                {
                    'id': None,
                    'nombre': 'Etapa Test 1',
                    'orden': 1,
                    'color_capa': '#10b981',
                    'coordenadas': [
                        [-31.4645, -64.3620],
                        [-31.4650, -64.3630],
                        [-31.4660, -64.3640]
                    ]
                }
            ],
            'comercios_adheridos': [
                {
                    'id': comercio.id,
                    'subcircuito_id': None
                }
            ]
        }

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('panel_circuito_guardar_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('ok'))
        circuito_id = data.get('circuito_id')

        # Comprobar en base de datos
        circuito_creado = CircuitoGeneral.objects.get(id=circuito_id)
        self.assertEqual(circuito_creado.nombre, 'Circuito Nuevo Test')
        self.assertTrue(circuito_creado.activo)

        # Comprobar etapa y trazado
        self.assertEqual(circuito_creado.subcircuitos.count(), 1)
        sub = circuito_creado.subcircuitos.first()
        self.assertEqual(sub.nombre, 'Etapa Test 1')
        self.assertEqual(sub.trazado.count(), 3)

        # Comprobar comercio adherido
        comercio.refresh_from_db()
        self.assertEqual(comercio.circuito_general, circuito_creado)

    def test_circuito_activar(self):
        """Activar y alternar un circuito debe actualizar activo entre True y False."""
        c2 = CircuitoGeneral.objects.create(nombre="Segundo Circuito", activo=False)
        self.client.force_login(self.admin_user)
        # 1. Activar
        response = self.client.post(reverse('panel_circuito_activar', kwargs={'pk': c2.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        c2.refresh_from_db()
        self.assertTrue(c2.activo)

        # 2. Desactivar (toggle)
        response_toggle = self.client.post(reverse('panel_circuito_activar', kwargs={'pk': c2.id}), follow=True)
        self.assertEqual(response_toggle.status_code, 200)
        c2.refresh_from_db()
        self.assertFalse(c2.activo)

    def test_circuito_delete(self):
        """Eliminar un circuito vía POST."""
        c = CircuitoGeneral.objects.create(nombre="Circuito a Borrar")
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('panel_circuito_eliminar', kwargs={'pk': c.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CircuitoGeneral.objects.filter(id=c.id).exists())


class PanelNoticiasTests(TestCase):
    """
    Suite de pruebas para el módulo de Gestión de Noticias del Panel de Administración.
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_noticias',
            email='admin_noticias@malagueno.gob.ar',
            password='password123',
            first_name='Admin',
            last_name='Noticias'
        )
        self.client.force_login(self.admin_user)

        # Crear noticias de prueba
        self.noticia_pub = Noticia.objects.create(
            titulo="Nueva ciclovía en Malagueño",
            contenido="Detalle sobre la inauguración de la ciclovía.",
            categoria="Urbanismo",
            autor_nombre="Carlos Ruiz",
            estado="Publicado",
            vistas=150
        )
        self.noticia_borr = Noticia.objects.create(
            titulo="Borrador de alerta vial",
            contenido="Trabajos de mantenimiento en la calzada.",
            categoria="Seguridad",
            autor_nombre="Elena Gómez",
            estado="Borrador",
            vistas=10
        )
        self.noticia_arch = Noticia.objects.create(
            titulo="Resultados carrera 2024",
            contenido="Historial de la competición del año anterior.",
            categoria="Eventos",
            autor_nombre="Pedro Sánchez",
            estado="Archivado",
            vistas=300
        )

    def test_noticias_listado_render(self):
        """El listado de noticias debe responder con 200 y mostrar KPIs y filas."""
        response = self.client.get(reverse('panel_noticias_listado'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel/gestion_noticias/listado_noticias.html')
        self.assertContains(response, 'Gestión de Noticias')
        self.assertContains(response, 'Nueva ciclovía en Malagueño')
        self.assertContains(response, 'Carlos Ruiz')
        self.assertContains(response, 'Urbanismo')
        self.assertContains(response, 'Publicadas')
        self.assertContains(response, 'Borradores')

    def test_noticias_filtros_estado(self):
        """Los filtros por tab/estado deben filtrar correctamente los resultados."""
        # Solo publicadas
        resp_pub = self.client.get(reverse('panel_noticias_listado') + '?estado=Publicado')
        self.assertEqual(resp_pub.status_code, 200)
        self.assertContains(resp_pub, 'Nueva ciclovía en Malagueño')
        self.assertNotContains(resp_pub, 'Borrador de alerta vial')

        # Solo borradores
        resp_borr = self.client.get(reverse('panel_noticias_listado') + '?estado=Borrador')
        self.assertEqual(resp_borr.status_code, 200)
        self.assertContains(resp_borr, 'Borrador de alerta vial')
        self.assertNotContains(resp_borr, 'Nueva ciclovía en Malagueño')

    def test_noticias_filtro_busqueda(self):
        """La búsqueda por texto debe encontrar por título o autor."""
        resp = self.client.get(reverse('panel_noticias_listado') + '?q=Elena')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Borrador de alerta vial')
        self.assertNotContains(resp, 'Nueva ciclovía en Malagueño')

    def test_noticia_create_post(self):
        """Crear una noticia vía POST debe guardarla en base de datos."""
        data = {
            'titulo': 'Nueva Noticia Creada en Test',
            'categoria': 'Comunidad',
            'autor_nombre': 'Redactor Test',
            'estado': 'Publicado',
            'contenido': 'Contenido de prueba para la noticia recién creada.'
        }
        response = self.client.post(reverse('panel_noticia_nueva'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Noticia.objects.filter(titulo='Nueva Noticia Creada en Test').exists())
        noticia = Noticia.objects.get(titulo='Nueva Noticia Creada en Test')
        self.assertEqual(noticia.categoria, 'Comunidad')
        self.assertEqual(noticia.estado, 'Publicado')

    def test_noticia_edit_post(self):
        """Editar una noticia existente debe persistir los cambios."""
        data = {
            'titulo': 'Título Editado con Éxito',
            'categoria': 'Eventos',
            'autor_nombre': 'Carlos Ruiz Modificado',
            'estado': 'Archivado',
            'contenido': 'Contenido completamente renovado.'
        }
        response = self.client.post(
            reverse('panel_noticia_editar', kwargs={'pk': self.noticia_pub.id}),
            data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.noticia_pub.refresh_from_db()
        self.assertEqual(self.noticia_pub.titulo, 'Título Editado con Éxito')
        self.assertEqual(self.noticia_pub.categoria, 'Eventos')
        self.assertEqual(self.noticia_pub.estado, 'Archivado')

    def test_noticia_cambiar_estado(self):
        """Cambio de estado ágil desde el dropdown de acciones."""
        response = self.client.get(
            reverse('panel_noticia_cambiar_estado', kwargs={'pk': self.noticia_borr.id, 'nuevo_estado': 'Publicado'}),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.noticia_borr.refresh_from_db()
        self.assertEqual(self.noticia_borr.estado, 'Publicado')

    def test_noticia_delete(self):
        """Eliminar una noticia vía POST."""
        n_id = self.noticia_arch.id
        response = self.client.post(
            reverse('panel_noticia_eliminar', kwargs={'pk': n_id}),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Noticia.objects.filter(id=n_id).exists())

