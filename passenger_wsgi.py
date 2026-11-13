"""
Punto de entrada oficial para Phusion Passenger en cPanel / CloudLinux.
Inicializa PyMySQL para compatibilidad con MySQL 8.0, añade sys.path y expone WSGI.
"""
import os
import sys
import pymysql

# 1. Compatibilidad pura de PyMySQL sin requerir compilación de mysqlclient (C)
pymysql.install_as_MySQLdb()

# 2. Añadir el directorio raíz de la aplicación a sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 3. Módulo de configuración Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# 4. Exponer aplicación WSGI
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

