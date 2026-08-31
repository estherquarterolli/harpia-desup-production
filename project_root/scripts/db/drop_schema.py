import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
    cursor.execute("GRANT ALL ON SCHEMA public TO public;")
print("Schema public dropped and recreated successfully.")
