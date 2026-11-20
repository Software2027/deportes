"""
Configuración de Django para el proyecto core (Sistema de Movilidad y Ciclismo Municipal).
Optimizado para despliegue en cPanel (Phusion Passenger) y desarrollo local.
"""

import os
from pathlib import Path
import dotenv
import pymysql

# Inicializar PyMySQL como driver nativo para MySQL en cPanel / Passenger
pymysql.install_as_MySQLdb()

# Compatibilidad con MariaDB 10.4.x (XAMPP / servidores locales) en Django 5.x
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.mysql.features import DatabaseFeatures
BaseDatabaseWrapper.check_database_version_supported = lambda self: None
DatabaseFeatures.can_return_columns_from_insert = property(lambda self: bool(self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 5)))
DatabaseFeatures.can_return_rows_from_bulk_insert = property(lambda self: bool(self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 5)))


# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Clave secreta y modo de depuración (Configuración directa sin variables de entorno)
SECRET_KEY = 'django-insecure-ciclismo-muni-clave-secreta-2026-xyz'
DEBUG = True
ALLOWED_HOSTS = ['*']


# Definición de Aplicaciones
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Librerías de terceros
    'rest_framework',

    # Aplicaciones del Sistema
    'ciudadano.apps.CiudadanoConfig',
    'panel.apps.PanelConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ciudadano.context_processors.circuito_activo_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Configuración de Base de Datos (Configuración directa)
import sys

# Si se ejecutan pruebas automáticas o se fuerza SQLite, usar SQLite en memoria/archivo
if 'test' in sys.argv or os.environ.get('USE_MYSQL') == 'False':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'sistema_ciclismo',
            'USER': 'root',
            'PASSWORD': '',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }


# Validación de contraseñas desactivada para permitir cualquier clave sin restricciones
AUTH_PASSWORD_VALIDATORS = []


# Internacionalización y zona horaria (Argentina / Municipio)
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True


# Archivos Estáticos (CSS, JavaScript, Imágenes)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Archivos Multimedia (Imágenes de noticias y comercios subidas por admin)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Redirecciones de Autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'mapa_carrera'
LOGOUT_REDIRECT_URL = 'index'

# Seguridad y Expiración de Sesión por Inactividad (1 Hora = 3600 segundos)
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True


# Configuración de Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
