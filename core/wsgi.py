"""
WSGI config for core project.
Optimizado para cPanel Phusion Passenger con PyMySQL.
"""

import os
import pymysql

# Inicializar PyMySQL para Passenger en cPanel
pymysql.install_as_MySQLdb()

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()
